"""Reviewed, source-linked editorial scripts for this event, not generic generated facts."""

def scene(key, title, kicker, narration, events, source=None, start=0, metrics=None, chart=None):
    return dict(id=key, title=title, kicker=kicker, narration=narration, event_ids=events,
                source_id=("f1-" + source) if source else None, source_in=start,
                metrics=metrics or [], chart=chart)

def _sprint_plans():
    vertical = [
        scene("hook", "SINGAPORE\nUNRAVELLED", "20 LAPS / 3 TURNING POINTS",
              "Verstappen won Singapore's wet Sprint. But the result was shaped by a lost lead, a drying track, and a collision between team mates on the final lap.",
              ["E01","E04","E11","E12"], "1878660117633008506", 0,
              [["WINNER", "VERSTAPPEN"], ["WINNING MARGIN", "2.591s"]]),
        scene("start", "THE START\nCHANGED EVERYTHING", "LAP 1 / WET TRACK",
              "Rain delayed the start. Everyone began on intermediates. Russell beat Verstappen into Turn One, while Hamilton jumped from sixth to third.",
              ["E01","E02","E03"], "1878655716565678004", 0,
              [["RUSSELL", "P2 → P1"], ["HAMILTON", "P6 → P3"]]),
        scene("crash", "A LEAD LOST\nIN ONE CORNER", "LAP 1 / FINAL CORNER",
              "Russell then crashed at the final corner of lap one. Verstappen inherited the lead. The Safety Car reset the race, but Russell's points chance was over.",
              ["E04","E06"], "1878656351618049423", 0,
              [["RUSSELL", "DNF"], ["NEW LEADER", "VERSTAPPEN"]]),
        scene("pace", "CONTROL\nAS THE TRACK DRIED", "RESTART → FINISH",
              "Racing resumed after lap six. Verstappen held Hamilton behind, then built breathing room. Leclerc's worn front tyres left him exposed to the two McLarens.",
              ["E08","E09","E10"], metrics=[["LEADER", "VERSTAPPEN"], ["CHASE", "HAMILTON"]], chart="gap"),
        scene("contact", "McLAREN'S\nLAST-LAP COST", "LAP 20 / TURN 5",
              "On the final lap, Norris and Piastri made contact at Turn Five. Norris finished eighth. Piastri stopped and was classified fourteenth. The stewards took no further action.",
              ["E11"], "1878659297812319467", 0,
              [["NORRIS", "P8 / 1 POINT"], ["PIASTRI", "P14 / DNF"]]),
        scene("results", "THE FINAL\nORDER", "FIA FINAL CLASSIFICATION",
              "Verstappen won by two point five nine one seconds. Hamilton and Leclerc completed the podium. Antonelli finished fourth, just zero point three six seven seconds behind Leclerc.",
              ["E12"], metrics=[["P3 → P4 GAP", "0.367s"]], chart="results"),
        scene("takeaway", "SURVIVE.\nTHEN EXECUTE.", "THE SPRINT TAKEAWAY",
              "Only thirteen drivers completed all twenty laps. Singapore rewarded controlled execution as much as outright speed. Sources: Formula One, the F I A, and Open F One.",
              ["E12"], "1878660117633008506", 0,
              [["FULL DISTANCE", "13 DRIVERS"], ["DISTANCE", "20 LAPS"]]),
    ]
    landscape = [
        scene("hook", "SINGAPORE: THE TURNING POINTS", "SPRINT ANALYSIS / 10 OCTOBER 2026",
              "A wet Singapore Sprint ended with Verstappen ahead of two Ferraris. The winning margin was just two point five nine one seconds, but the story was much larger than that number. Three phases explain the result: the opening lap, the drying track, and a final lap that changed the points.",
              ["E01","E04","E11","E12"], "1878660117633008506", 0,
              [["WINNER", "VERSTAPPEN"], ["MARGIN", "2.591s"], ["DISTANCE", "20 LAPS"]]),
        scene("start", "01 / A WET START, A NEW LEADER", "ACTUAL START / 17:36 SINGAPORE",
              "Rain forced a delay and two formation laps. When the race finally started, the field was on intermediate tyres. Russell launched past polesitter Verstappen into Turn One. Hamilton made the other major gain, moving from sixth on the grid to third. Both gains came before the race's first major reversal.",
              ["E01","E02","E03"], "1878655716565678004", 0,
              [["RUSSELL", "P2 → P1"], ["HAMILTON", "P6 → P3"], ["START TYRE", "INTERMEDIATE"]]),
        scene("crash", "02 / RUSSELL'S OPENING-LAP EXIT", "LAP 1 / FINAL CORNER",
              "At the final corner of the first lap, Russell lost control and hit the barrier. Verstappen inherited the lead and Hamilton moved into second. This was the decisive reversal at the front. Russell's strong getaway now counted for nothing, while Verstappen had another chance to control the race.",
              ["E04"], "1878656351618049423", 0,
              [["RUSSELL", "DNF"], ["VERSTAPPEN", "P1"], ["HAMILTON", "P2"]]),
        scene("attrition", "03 / CONTACT AT THE RESTART", "RESTART / END OF LAP 6",
              "The restart brought more trouble behind the leaders. Albon's Williams contacted Bortoleto's Audi, and Bottas then hit the Williams. Bortoleto and Bottas retired after the incident. Albon continued for a while, but also failed to finish. Three teams lost a chance to turn a difficult afternoon into points.",
              ["E07"], "1878658723525130166", 0,
              [["INVOLVED", "ALBON / BORTOLETO / BOTTAS"], ["OUTCOME", "ALL THREE RETIRED"]]),
        scene("pace", "04 / THE RACE BECOMES TYRE MANAGEMENT", "LAP 7 → LAP 20 / TIMING DATA",
              "Racing resumed after lap six. Hamilton initially stayed close, before Verstappen extended the gap as the surface dried. This chart compares their recorded lap finish times. It shows how the margin evolved, but it does not isolate how much came from tyres, traffic, or driver input. Those causal claims need more evidence.",
              ["E08","E09"], metrics=[["CHART", "HAM GAP TO VER"], ["UNITS", "SECONDS"], ["METHOD", "LAP FINISH TIMES"]], chart="gap"),
        scene("pressure", "05 / THE PODIUM BATTLE TIGHTENS", "CLOSING LAPS / LECLERC UNDER PRESSURE",
              "Behind Hamilton, Leclerc was struggling with front tyre wear. Piastri and Norris closed in, with Antonelli also in the fight. That made the closing laps a contest over the final podium place. Leclerc ultimately kept third, finishing just zero point three six seven seconds ahead of Antonelli.",
              ["E10","E12"], metrics=[["LECLERC", "+16.871s"], ["ANTONELLI", "+17.238s"], ["BETWEEN THEM", "0.367s"]], chart="podium"),
        scene("contact", "06 / McLAREN'S FINAL-LAP COLLISION", "LAP 20 / TURN 5",
              "At Turn Five on the last lap, the McLarens made contact. Norris recovered to finish eighth and score one point. Piastri could not finish, although he was classified fourteenth after completing nineteen laps. The stewards reviewed the collision and took no further action. A promising podium chase had become a painful result.",
              ["E11"], "1878659297812319467", 0,
              [["NORRIS", "P8 / 1 POINT"], ["PIASTRI", "P14 / DNF"], ["STEWARDS", "NO FURTHER ACTION"]]),
        scene("result", "07 / WHAT THE RESULT CHANGES", "FIA FINAL CLASSIFICATION + POINTS",
              "Verstappen took eight points, Hamilton seven and Leclerc six. Antonelli's fourth place added five, extending his championship advantage over Russell from eighty four points to eighty nine. Only thirteen drivers completed all twenty laps. The final classification records nine drivers with D N F status, including the classified Piastri.",
              ["E12","E13"], metrics=[["ANTONELLI LEAD", "84 → 89 POINTS"], ["DNF STATUS", "9 DRIVERS"]], chart="results"),
        scene("outro", "CONTROL WAS THE DIFFERENCE", "SOURCES / FIA · FORMULA 1 · OPENF1",
              "The lesson from this Sprint is execution under changing conditions. Verstappen recovered from losing the start, avoided the incidents, and managed the lead to the flag. Ferrari took two podium places, while Antonelli strengthened his championship position. Singapore's short race delivered a big reminder: first, you have to reach the finish.",
              ["E03","E09","E12"], "1878660117633008506", 0,
              [["WINNER", "MAX VERSTAPPEN"], ["SOURCE FILES", "IN THE LOCAL LIBRARY"]]),
    ]
    return {"vertical": {"idea_id": "I01", "title": "Singapore Sprint — Three turning points", "scenes": vertical},
            "landscape": {"idea_id": "I01", "title": "Singapore Sprint — The race explained", "scenes": landscape}}

def plans():
    """New events require their own researched script; never relabel an old plan."""
    from .core import ROOT, config, read_json
    path=ROOT/'research/event/video_plan.json'
    if path.exists():
        value=read_json(path)
        if value.get('event_id') != config()['id']:
            raise ValueError('Video plan event identity mismatch')
        formats=value.get('formats')
        if not isinstance(formats,dict) or not formats:
            raise ValueError('Video plan requires named formats')
        return formats
    if config()['id']=='2026-singapore-sprint':
        return _sprint_plans()
    raise ValueError('New event requires research/event/video_plan.json')
