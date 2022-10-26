import logging
import re
import shelve
import warnings

import fontFeatures
import tqdm
from beziers.point import Point
from collidoscope import Collidoscope
from fez import FEZVerb
from fontFeatures.shaperLib.Buffer import Buffer
from fontFeatures.shaperLib.Shaper import Shaper
from glyphtools import get_glyph_metrics

from karakul.NastaliqConnections import load_rules

# logging.basicConfig(format='%(message)s')
# logging.getLogger("fontFeatures.shaperLib").setLevel(logging.DEBUG)


PARSEOPTS = dict(use_helpers=True)

GRAMMAR = ""

AddSpacedAnchors_GRAMMAR = """
?start: action
action: valuerecord_number
"""

DetectAndSwap_GRAMMAR = """
?start: action
action: BARENAME BARENAME?
"""

VERBS = ["AddSpacedAnchors", "DetectAndSwap"]

taskil_above = ["DAMMA"]
taskil_below = ["KASRA"]

max_sequence_length = 3
max_run = 200
margin = 0


class AddSpacedAnchors(FEZVerb):
    def action(self, args):
        (spacing,) = args
        spacing = spacing.resolve_as_integer()
        anchors = self.parser.fontfeatures.anchors
        glyphs = self.parser.font.exportedGlyphs()
        for g in glyphs:
            if g not in anchors: continue
            this_anchors = anchors.get(g,{})
            if "top" in this_anchors:
                topx, topy = this_anchors["top"]
                this_anchors["top.one"] = topx, topy + spacing
                this_anchors["top.two"] = topx, topy + spacing * 2
            if "bottom" in this_anchors:
                bottomx, bottomy = this_anchors["bottom"]
                this_anchors["bottom.one"] = bottomx, bottomy - spacing
                this_anchors["bottom.two"] = bottomx, bottomy - spacing * 2
            if "comma" in this_anchors:
                commax, commay = this_anchors["comma"]
                this_anchors["comma.one"] = commax, commay - spacing
                this_anchors["comma.two"] = commax, commay - spacing * 2

        return []

class DetectAndSwap(FEZVerb):
    def action(self, args):
        self.anchor = args[0]
        self.reverse = len(args) == 2
        warnings.warn("%s, %s" % (self.anchor, self.reverse))
        if self.anchor == "bottom":
            self.dots = ["haydb", "sdb", "sdb.one", "sdb.two", "ddb", "ddb.one", "ddb.two", "tdb", "tdb.one", "tdb.two"] + taskil_below
        else:
            self.dots = ["toeda", "sda", "sda.one", "sda.two", "dda", "dda.one", "dda.two", "tda", "tda.one", "tda.two", "HAMZA_ABOVE"] + taskil_above


        self.shelve = shelve.open("collisioncache.db")
        self.c = Collidoscope("Gulzar", { "marks": True, "bases": False, "faraway": True}, ttFont=self.parser.font, scale_factor = 1.22)
        self.contexts = self.get_contexts()
        seq = self.generate_glyph_sequence(max_sequence_length)
        drop_one = fontFeatures.Routine(
            name = "cycle_dots_1_"+self.anchor,
        )
        drop_two = fontFeatures.Routine(
            name = "cycle_dots_2_"+self.anchor,
        )
        drop_three = fontFeatures.Routine(
            name = "cycle_dots_3_"+self.anchor,
        )

        for dot in self.dots:
            nextdot = self.cycle(dot)
            if nextdot in self.parser.font.glyphs:
                drop_one.rules.append(fontFeatures.Substitution(
                    [[dot]], [[nextdot]]
                ))
                nextdot = self.cycle(nextdot)
                if nextdot in self.parser.font.glyphs:
                    drop_two.rules.append(fontFeatures.Substitution(
                        [[dot]], [[nextdot]]
                    ))
                    nextdot = self.cycle(nextdot)
                    if nextdot in self.parser.font.glyphs:
                        drop_three.rules.append(fontFeatures.Substitution(
                            [[dot]], [[nextdot]]
                        ))

        count = 0
        mitigated_count = 0
        rules = set({})
        result = []
        nc = self.parser.fontfeatures.namedClasses
        self.parser.fontfeatures.namedClasses = {}

        for sequence in tqdm.tqdm(seq):
            if tuple(sequence) in rules:
                continue
            collides = self.collides(sequence)
            if collides:
                mitigated = self.try_mitigate(sequence)
                count += 1
                if mitigated:
                    mitigated_count += 1
                    dot_position, orig_dot, newdot, times = mitigated
                    goto = drop_one
                    if times == 2:
                        goto = drop_two
                    if times == 3:
                        goto = drop_three
                    rules.add(tuple(sequence))
                    if self.reverse:
                        result.append(fontFeatures.Substitution(
                            [[orig_dot]],
                            [[newdot]],
                            # lookups=[[self.parser.fontfeatures.referenceRoutine(goto)]],
                            precontext=[[x] for x in sequence[:dot_position]],
                            postcontext=[[x] for x in sequence[dot_position+1:]],
                            reverse=True
                        ))
                    else:
                        result.append(fontFeatures.Chaining(
                            [[sequence[dot_position-1]],[orig_dot]],
                            lookups=[None, [self.parser.fontfeatures.referenceRoutine(goto)]],
                            precontext=[[x] for x in sequence[:dot_position-1]],
                            postcontext=[[x] for x in sequence[dot_position+1:]]
                        ))
                # else:
                #     warnings.warn("Nothing helped %s" % sequence)
        warnings.warn("At %s, fixed %i/%i collisions" % (str(self.anchor), mitigated_count, count))
        self.parser.fontfeatures.namedClasses = nc
        self.shelve.close()

        if self.reverse:
            name="DotAvoidance_reverse_"+self.anchor
        else:
            name="DotAvoidance_"+self.anchor

        return [fontFeatures.Routine(
            name = name,
            rules = result,
            flags = 0x10,
            markFilteringSet = self.dots
        )]

    def collides(self, glyphs):
        key = "/".join(glyphs)
        if key not in self.shelve:
            pos = self.position_glyphs(glyphs)
            pos = [x for x in pos if x["category"] == "mark"]
            # if any(["toeda" in g["name"] or "HAMZA_ABOVE" in g["name"] for g in pos]):
            self.shelve[key] = bool(self.c.has_collisions(pos))
        return self.shelve[key]

        # for ix in range(len(pos)):
        #     if pos[ix]["category"] != "mark":
        #         continue
        #     gb1 = pos[ix]["glyphbounds"]
        #     gb1.addMargin(margin)
        #     for jx in range(ix+1, len(pos)):
        #         if pos[jx]["category"] != "mark":
        #             continue
        #         gb2 = pos[jx]["glyphbounds"]
        #         gb2.addMargin(margin)
        #         if gb1.overlaps(gb2):
        #             return True
        # return False

    def try_mitigate(self, glyphs):
        newglyphs = list(glyphs)
        if not any(x in self.dots for x in glyphs):
            return
        if self.reverse:
            move_position = [x in self.dots for x in glyphs].index(True)
        else:
            move_position = len(glyphs) - 1 - ([x in self.dots for x in glyphs])[::-1].index(True)

        orig_dot = glyphs[move_position]
        for times in range(1, 4):
            newdot = self.cycle(newglyphs[move_position])
            if newdot == orig_dot:
                return
            if not newdot or newdot not in self.parser.font.glyphs:
                return
            newglyphs[move_position] = newdot
            # Check it again
            if not self.collides(newglyphs):
                return move_position, orig_dot, newdot, times

    def cycle(self, dot):
        if dot.endswith(".two"):
            return dot[:-4]
        if dot.endswith(".one"):
            return dot[:-4] + ".two"
        else:
            return dot+".one"


    def draw(self, glyphs):
        positioned_glyphs = self.position_glyphs(glyphs)
        import matplotlib.pyplot as plt
        from beziers.path.geometricshapes import Rectangle
        fig, ax = plt.subplots()
        ax.set_aspect("equal")
        for g in positioned_glyphs:
            for p_ in g["paths"]:
                p_.plot(ax, drawNodes=True,fill=True)
            for pb in g["pathbounds"]:
                rect = Rectangle(pb.width, pb.height, pb.centroid)
                rect.plot(ax, drawNodes=False,fill=False)
        plt.show()

    def position_glyphs(self, glyphs):
        layers = [self.parser.font.default_master.get_glyph_layer(g) for g in glyphs]
        positions = [
            {"xPlacement": 0, "yPlacement": 0, "xAdvance": l.width} for l in layers
        ]
        # Do cursive attachment first

        exit_anchor = layers[0].anchors_dict.get("exit", Point(0, 0))
        if "entry" in layers[2].anchors_dict and "exit" in layers[0].anchors_dict:
            positions[2]["xAdvance"] = layers[2].anchors_dict["entry"].x
            positions[0]["xPlacement"] -= layers[0].anchors_dict["exit"].x
            positions[1]["xPlacement"] -= layers[0].anchors_dict["exit"].x
            positions[0]["yPlacement"] = layers[2].anchors_dict["entry"].y - layers[0].anchors_dict["exit"].y
            positions[1]["yPlacement"] = layers[2].anchors_dict["entry"].y - layers[0].anchors_dict["exit"].y

        # Then do mark attachment
        positions[1]["xAdvance"] = 0
        positions[3]["xAdvance"] = 0
        anchors = [self.parser.fontfeatures.anchors.get(g, {}) for g in glyphs]
        match_1 = list(set(anchors[0].keys()) & set(x[1:] for x in anchors[1].keys()))
        if not match_1:
            warnings.warn("No matching anchors for %s/%s" % (glyphs[0], glyphs[1]))
            return []
        match_1 = match_1[0]
        match_2 = list(set(anchors[2].keys()) & set(x[1:] for x in anchors[3].keys()))
        if not match_2:
            warnings.warn("No matching anchors for %s/%s" % (glyphs[2], glyphs[3]))
            return []
        match_2 = match_2[0]

        pair_1 = (anchors[0][match_1], anchors[1]["_"+match_1])
        pair_2 = (anchors[2][match_2], anchors[3]["_"+match_2])
        try:
            a = pair_1[0][0]
            a = pair_1[0][1]
        except Exception as e:
            raise ValueError("Glyph %s missing %s anchor" % (glyphs[0], match_1))
        try:
            b = pair_1[1][0]
            b = pair_1[1][1]
        except Exception as e:
            raise ValueError("Glyph %s missing %s anchor" % (glyphs[1], "_"+match_1))
        try:
            c = pair_2[0][0]
            c = pair_2[0][1]
        except Exception as e:
            raise ValueError("Glyph %s missing %s anchor" % (glyphs[2], match_2))
        try:
            g = pair_2[1][0]
            g = pair_2[1][1]
        except Exception as e:
            raise ValueError("Glyph %s missing %s anchor" % (glyphs[3], "_"+match_2))

        # If they are variable, just choose the default
        for ix_1 in range(0,2):
            for ix_2 in range(0,2):
                if not isinstance(pair_1[ix_1][ix_2], (int,float)):
                    pair_1[ix_1][ix_2] = pair_1[ix_1][ix_2].default
                if not isinstance(pair_2[ix_1][ix_2], (int,float)):
                    pair_2[ix_1][ix_2] = pair_2[ix_1][ix_2].default

        positions[1]["xPlacement"] += (pair_1[0][0] - pair_1[1][0])
        positions[1]["yPlacement"] += pair_1[0][1] - pair_1[1][1]

        positions[3]["xPlacement"] += (pair_2[0][0] - pair_2[1][0])
        positions[3]["yPlacement"] += pair_2[0][1] - pair_2[1][1]

        cursor = 0
        outglyphs = []
        for position,glyph in zip(reversed(positions),reversed(glyphs)):
            placement = Point(cursor + position["xPlacement"], position["yPlacement"])
            g = self.c.get_positioned_glyph(glyph, placement)
            outglyphs.append(g)
            cursor += position["xAdvance"]
        return outglyphs

    def get_contexts(self):
        rules = load_rules("sources/build/rules.csv", self.parser.font.exportedGlyphs(), full=True)
        # possible = set([])
        self.rasm_glyphs = set([])
        possible_contexts = {}

        for old in rules:
            for new in rules[old]:
                for context in rules[old][new]:
                    # possible.add((new, context))
                    possible_contexts.setdefault(new,[]).append(context)
                    self.rasm_glyphs.add(new)
                    self.rasm_glyphs.add(context)
        return possible_contexts

    def generate_glyph_sequence(self, n):
        thin = [x for x in self.parser.font.exportedGlyphs() if get_glyph_metrics(self.parser.font,x)["run"] < max_run and re.search(r"m\d+$", x)]
        if self.reverse:
            sda = ["sda"]
            dda = ["dda"]
            tda = ["tda"]
            sdb = ["sdb"]
            ddb = ["ddb"]
            tdb = ["tdb"]
        else:
            sda = ["sda", "sda.one", "sda.two"]
            dda = ["dda", "dda.one", "dda.two"]
            tda = ["tda", "tda.one", "tda.two"]
            sdb = ["sdb", "sdb.one", "sdb.two"]
            ddb = ["ddb", "ddb.one", "ddb.two"]
            tdb = ["tdb", "tdb.one", "tdb.two"]

        dot_combinations = {
            "HAYC": (["dda", "HAMZA_ABOVE"], ["haydb"]),
            "HAYA": (["HAMZA_ABOVE"],[]),
            "VAO": (["HAMZA_ABOVE"],[]),
            "SIN": (tda, []),
            "BE": (dda+tda+["toeda", "HAMZA_ABOVE"], sdb+ddb+tdb),
            "SAD": (sda, []),
            "DAL": (sda+["toeda"], []),
            "RE": (sda + tda + ["toeda", "HAMZA_ABOVE"], []),
            "AIN": (sda, []),
            "FE": (sda+dda, []),
            "QAF": (dda, []),
            "TOE": (sda, []),
            "JIM": (sda+["HAMZA_ABOVE"], sdb+tdb),
            "MIM": ([],[]),
            "KAF": ([],[]),
            "GAF": ([],[]),
            "LAM": ([],[]),
        }

        def dotsfor(t):
            dots = []
            for k,v in dot_combinations.items():
                if k in t:
                    if self.anchor == "top":
                        if self.reverse:
                            return v[0]
                        else:
                            return v[0] + taskil_above
                    else:
                        if self.reverse:
                            return v[1]
                        else:
                            return v[1] + taskil_below
            if self.reverse:
                return []
            if self.anchor == "top":
                return taskil_above
            else:
                return taskil_below

        stems = dot_combinations.keys()
        stem_re = r"^(" + ("|".join(stems)) + r")[mif]"
        starters = [x for x in self.parser.font.exportedGlyphs() if re.match(stem_re,x)]

        sequences = []
        for left in list(set(starters) & set(self.rasm_glyphs)):
#            for mid in list(set(self.contexts.get(left,[])) & set(thin)):
#                for right in list(set(self.contexts.get(mid,[])) & set(starters)):
#                    for left_dot in dotsfor(left):
#                        for right_dot in dotsfor(right):
#                            sequences.append([left, left_dot, mid, right, right_dot ])
            for right in list(set(self.contexts.get(left,[])) & set(self.rasm_glyphs)):
                for left_dot in dotsfor(left):
                    if left_dot == "dda" and left.startswith("HAYC") and left != "HAYCf1":
                        continue
                    for right_dot in dotsfor(right):
                        if right_dot == "dda" and right.startswith("HAYC") and right != "HAYCf1":
                            continue
                        sequences.append([left, left_dot, right, right_dot ])
        return sequences

