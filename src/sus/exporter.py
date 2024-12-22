import custom_sus_io as csus
from typing import cast
from src.notes.score import Score
from src.notes.bpm import Bpm
from src.notes.timescale import TimeScaleGroup, TimeScalePoint
from src.notes.single import Single
from src.notes.slide import Slide, SlideStartPoint, SlideRelayPoint, SlideEndPoint
from src.notes.guide import Guide, GuidePoint


class SusNoteType:
    class Tap:
        TAP = 1
        C_TAP = 2
        FLICK = 3
        TRACE = 5
        C_TRACE = 6
        ELASER = 7
        C_ELASER = 8


    class Air:
        UP = 1
        DOWN = 2
        LEFT_UP = 3
        RIGHT_UP = 4
        LEFT_DOWN = 5
        RIGHT_DOWN = 6


    class Slide:
        START = 1
        END = 2
        VISIBLE_STEP = 3 # 可視中継点
        STEP = 5


    class Guide:
        START = 1
        END = 2
        STEP = 5


# beatをtickに変換する
def beat_to_tick(beat: float) -> int:
    return round(480 * beat)

# uscのレーン記法からsusのレーン記法に変換する
def usc_lanes_to_sus_lanes(lane: float, size: float) -> int:
    return int(lane - size + 8)

# uscのノーツサイズ記法からsusのノーツサイズ記法に変換する
def usc_notesize_to_sus_notesize(size: float) -> int:
    #if size % 0.5 != 0:
    #    Exception("小数幅が検出されました")
    return int(size * 2)

def export(path: str, score: Score):
    metadata = score.metadata
    notes = score.notes
    taps = []
    directionals = []
    slides = []
    guides = []
    bpms = []
    tils = []

    for note in notes:
        if isinstance(note, Bpm):
            tick = beat_to_tick(note.beat)
            bpms.append((tick, note.bpm))

        elif isinstance(note, TimeScaleGroup):
            note = cast(TimeScaleGroup, note)
            for changepoint in note.changes:
                changepoint = cast(TimeScalePoint, changepoint)
                tick = beat_to_tick(changepoint.beat)
                bar = tick // 1920
                tick = tick % 1920
                tils.append(f"{bar}'{tick}:{changepoint.timeScale}")

        elif isinstance(note, Single):
            lane = usc_lanes_to_sus_lanes(note.lane, note.size)
            width = usc_notesize_to_sus_notesize(note.size)
            tick = beat_to_tick(note.beat)
            if note.trace: # トレース or 金トレース
                if note.critical:
                    taps.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Tap.C_TRACE) )
                else:
                    taps.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Tap.TRACE) )
            else: # タップ or 金タップ
                if note.critical:
                    taps.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Tap.C_TAP) )
                else:
                    taps.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Tap.TAP) )
            if note.direction: # フリック付
                if note.direction == "up":
                    directionals.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Air.UP) )
                elif note.direction == "left":
                    directionals.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Air.LEFT_UP) )
                elif note.direction == "right":
                    directionals.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Air.RIGHT_UP) )
        
        elif isinstance(note, Slide):
            slide = []
            note.connections.sort(key= lambda x: x.beat)
            for step in note.connections:
                tick = beat_to_tick(step.beat)
                lane = usc_lanes_to_sus_lanes(step.lane, step.size)
                width = usc_notesize_to_sus_notesize(step.size)
                # 始点
                if step.type == "start": 
                    step = cast(SlideStartPoint, step)
                    if step.ease == "in": # 加速
                        directionals.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Air.DOWN) )
                    elif step.ease == "out": # 減速
                        directionals.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Air.RIGHT_DOWN) )
                    elif step.ease == "linear": # 直線
                        pass
                    if step.judgeType == "none": # 始点消し
                        if step.critical:
                            taps.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Tap.C_ELASER) )
                        else:
                            taps.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Tap.ELASER) )
                    elif step.judgeType == "trace": # 始点トレース
                        if step.critical:
                            taps.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Tap.C_TRACE) )
                        else:
                            taps.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Tap.TRACE) )
                    elif step.judgeType == "normal":
                        if step.critical:
                            taps.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Tap.C_TAP) )
                    slide.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Slide.START) )

                # 中継点
                elif step.type in ("tick", "attach"):
                    step = cast(SlideRelayPoint, step)
                    if step.ease == "in": # 加速
                        taps.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Tap.TAP) )
                        directionals.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Air.DOWN) )
                    elif step.ease == "out": # 減速
                        taps.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Tap.TAP) )
                        directionals.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Air.RIGHT_DOWN) )
                    elif step.ease == "linear": # 直線
                        pass
                    if step.type == "tick":  
                        if step.critical == None: # 不可視中継点 
                            slide.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Slide.STEP) )
                        else: # 可視中継点
                            slide.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Slide.VISIBLE_STEP) )
                    elif step.type == "attach": # 無視中継点
                        taps.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Tap.FLICK))
                        slide.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Slide.STEP) )

                # 終点
                elif step.type == "end":
                    step = cast(SlideEndPoint, step)
                    if step.judgeType == "none": # 終点消し
                        if step.critical:
                            taps.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Tap.C_ELASER) )
                        else:
                            taps.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Tap.ELASER) )
                    elif step.judgeType == "trace": # 終点トレース
                        if step.critical:
                            taps.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Tap.C_TRACE) )
                        else:
                            taps.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Tap.TRACE) )
                    elif step.judgeType == "normal":
                        if step.direction:
                            if step.critical:
                                taps.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Tap.C_TAP) )
                    if step.direction: # フリック付
                        if step.direction == "up":
                            directionals.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Air.UP) )
                        elif step.direction == "left":
                            directionals.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Air.LEFT_UP) )
                        elif step.direction == "right":
                            directionals.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Air.RIGHT_UP) )
                    slide.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Slide.END) )
            slides.append(slide)

        elif isinstance(note, Guide):
            guide = []
            note.midpoints.sort(key= lambda x: x.beat)
            point_length = len(note.midpoints)
            for idx, step in zip(range(point_length), note.midpoints):
                step = cast(GuidePoint, step)
                tick = beat_to_tick(step.beat)
                lane = usc_lanes_to_sus_lanes(step.lane, step.size)
                width = usc_notesize_to_sus_notesize(step.size)
                # 始点
                if idx == 0:
                    if note.color == "yellow":
                        taps.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Tap.C_ELASER) )
                    elif note.color == "green":
                        taps.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Tap.ELASER) )

                    if step.ease == "in": # 加速
                        directionals.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Air.UP) )
                    elif step.ease == "out": # 減速
                        directionals.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Air.RIGHT_DOWN) )
                    elif step.ease == "linear": # 直線
                        pass
                    guide.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Guide.START) )

                # 終点
                elif idx == point_length-1:
                    if note.color == "yellow":
                        taps.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Tap.C_ELASER) )
                    elif note.color == "green":
                        pass
                    guide.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Guide.END) )

                # 中継点
                else:
                    if step.ease == "in": # 加速
                        if note.color == "yellow":
                            taps.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Tap.C_ELASER) )
                        elif note.color == "green":
                            taps.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Tap.ELASER) )
                        directionals.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Air.DOWN) )
                    elif step.ease == "out": # 減速
                        if note.color == "yellow":
                            taps.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Tap.C_ELASER) )
                        elif note.color == "green":
                            taps.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Tap.ELASER) )
                        directionals.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Air.RIGHT_DOWN) )
                    elif step.ease == "linear": # 直線
                        if note.color == "yellow":
                            taps.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Tap.C_ELASER) )
                        elif note.color == "green":
                            pass
                    guide.append( csus.Note(tick=tick, lane=lane, width=width, type=SusNoteType.Guide.STEP) )
            guides.append(guide)

    sus_metadata = csus.Metadata(
        title=metadata.title,
        artist=metadata.artist,
        designer=metadata.designer,
        waveoffset=metadata.waveoffset
    )

    sus_text = csus.dumps(
        csus.Score(
            metadata=sus_metadata,
            taps=taps,
            directionals=directionals,
            slides=slides,
            guides=guides,
            bpms=bpms,
            bar_lengths=[(0, 4.0)]
        ),
        comment="This file was generated by SUSC Tools 0.1.0",
        space=False
    )
            
    with open(path, "w", encoding="UTF-8") as f:
        f.write(sus_text)
        f.write(f'#TIL00: "{", ".join(tils)}"\n')
        f.write("#HISPEED 00\n")
        f.write("#MEASUREHS 00\n")