"""
MIT License

Copyright (c) 2021 mkpoli

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import base36
import math

from . import __version__
from .schemas import Score, BarLength

from collections import defaultdict
from typing import Optional, TextIO, Union
from dataclasses import fields

class ChannelProvider:
    channel_map: dict[int, tuple[int, int]]
    
    def __init__(self):
        self.channel_map = { key: (0, 0) for key in range(36) }
    
    def generate_channel(self, start_tick: int, end_tick: int) -> int:
        for key, (start, end) in self.channel_map.items():
            if (start == 0 and end == 0) or end_tick < start or end < start_tick:
                self.channel_map[key] = (start_tick, end_tick)
                return key
        raise Exception('No more channel available.')

def dump(score: Score, fp: TextIO, **kw) -> None:
    """
    Dump a Score object into a SUS file.
    
    :param score: The score object to dump.
    :param score: The score object to dump.
    :param space: Whether to add a space after the tag (with space: "#00010: 00", without: "#00010:00").
    """
    fp.write(dumps(score, **kw))

def format_number(value: float) -> str:
    """
    Format a number into a string, where “.0” is removed if number does not have a decimal part.

    :param value: The number to format.
    """
    return str(int(value) if value % 1 == 0 else value)

def format_value(value: Union[str, float], is_str: bool) -> str:
    return f'"{value}"' if is_str else format_number(value)

def dumps(
    score: Score,
    comment: str=f'This file was generated by sus-io v{__version__} (Python).',
    space = False
) -> str:
    """
    Dump a Score object into a string in SUS format.
    
    :param score: The score object to dump.
    :param space: Whether to add a space after the tag (with space: "#00010: 00", without: "#00010:00").
    :return: SUS data as a string.
    """
    lines = []
    
    # Metadata
    lines.append(comment)
    
    ticks_per_beat = 480
    for field in fields(score.metadata):
        attr = getattr(score.metadata, field.name)
        if attr is None:
            continue
        if field.name != 'requests':
            lines.append(f'#{field.name.upper()} {format_value(attr, field.type is Optional[str])}')
        else:
            lines.append('')
            for request in score.metadata.requests:
                lines.append(f'#REQUEST "{request}"')
                if request.startswith('ticks_per_beat'):
                    ticks_per_beat = int(request.split()[1])
    lines.append('')
    
    # Scoredata
    note_maps = defaultdict(lambda: { 'raws': [], 'ticks_per_measure': 0 })
    
    bar_lengths = sorted(score.bar_lengths, key=lambda x: x[0])
    bpms = sorted(score.bpms, key=lambda x: x[0])
    taps = sorted(score.taps, key=lambda note: note.tick)
    directionals = sorted(score.directionals, key=lambda note: note.tick)
    slides = sorted(score.slides, key=lambda x: x[0].tick)
    guides = sorted(score.guides, key=lambda x: x[0].tick)
    tils = sorted(score.tils, key=lambda x: x[0])

    for measure, value in bar_lengths:
        lines.append(f'#{measure:03}02:{" " if space else ""}{format_number(value)}')
    lines.append('')

    accumulated_ticks = 0
    
    bar_lengths_in_ticks = []
    
    for index, (measure, value) in enumerate(bar_lengths):
        nextMeasure = bar_lengths[index + 1][0] if index + 1 < len(bar_lengths) else 0
        start_tick = accumulated_ticks
        accumulated_ticks += int((nextMeasure - measure) * value * ticks_per_beat)
        bar_lengths_in_ticks.append(BarLength(start_tick, measure, value))
    
    bar_lengths_in_ticks.reverse()
    
    def push_raw(tick: int, info: str, data: str):
        for bar_length in bar_lengths_in_ticks:
            if tick >= bar_length.start_tick:
                current_measure = bar_length.measure + int((tick - bar_length.start_tick) / ticks_per_beat / bar_length.value)
                note_map = note_maps[f'{current_measure:03}{info}']
                note_map['raws'].append([tick - bar_length.start_tick, data])
                note_map['ticks_per_measure'] = int(bar_length.value * ticks_per_beat)
                break
    
    if len(bpms) >= 36 ** 2 - 1:
        raise Exception(f'Too much BPMS ({bpms.length} >= 36^2 -1 = {36 ** 2 - 1})')

    bpm_identifiers = {}
    for tick, value in bpms:
        identifier = base36.dumps(len(bpm_identifiers) + 1).zfill(2)
        if value not in bpm_identifiers:
            bpm_identifiers[value] = identifier
            lines.append(f'#BPM{bpm_identifiers[value]}:{" " if space else ""}{format_number(value)}')
        push_raw(tick, '08', bpm_identifiers[value])
    lines.append('')

    # ハイスピ(dumper側は変拍子対応が不要のため未対応)
    til_list = []
    for tick, value in tils:
        til_list.append(f"{tick//(ticks_per_beat*4)}'{tick%(ticks_per_beat*4)}:{value}")
    lines.append('#TIL00: "' + f"{', '.join(til_list)}" + '"')
    lines.append('#HISPEED 00')
    lines.append('#MEASUREHS 00')
    lines.append('')

    for note in taps:
        push_raw(note.tick, f'1{base36.dumps(note.lane)}', f'{note.type}{base36.dumps(note.width)}')

    for note in directionals:
        push_raw(note.tick, f'5{base36.dumps(note.lane)}', f'{note.type}{base36.dumps(note.width)}')

    slide_provider = ChannelProvider()
    for steps in slides:
        start_tick = steps[0].tick
        end_tick = steps[-1].tick
        channel = slide_provider.generate_channel(start_tick, end_tick)
        for note in steps:
            push_raw(note.tick, f'3{base36.dumps(note.lane)}{base36.dumps(channel)}', f'{note.type}{base36.dumps(note.width)}')

    # ガイドノーツに対応
    guide_provider = ChannelProvider()
    for steps in guides:
        start_tick = steps[0].tick
        end_tick = steps[-1].tick
        channel = guide_provider.generate_channel(start_tick, end_tick)
        for note in steps:
            push_raw(note.tick, f'9{base36.dumps(note.lane)}{base36.dumps(channel)}', f'{note.type}{base36.dumps(note.width)}')
    
    for tag, note_map in note_maps.items():
        gcd = note_map['ticks_per_measure']
        for raw in note_map['raws']:
            gcd = math.gcd(raw[0], gcd)
        data = {}
        for raw in note_map['raws']:
            data[(raw[0] % note_map['ticks_per_measure'])] = raw[1]
        values = []
        for i in range(0, note_map['ticks_per_measure'], gcd):
            values.append(data.get(i) or '00')
        lines.append(f'#{tag}:{" " if space else ""}{"".join(values)}')

    lines.append('')

    return '\n'.join(lines)
