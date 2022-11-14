import os
import csv
import re
import fontFeatures
import warnings

from fez import FEZVerb

PARSEOPTS = dict(use_helpers=True)

GRAMMAR = ""

NastaliqConnections_GRAMMAR = """
?start: action
action: ESCAPED_STRING glyphselector?
"""

FinalSelection_GRAMMAR = """
?start: action
action: ESCAPED_STRING glyphselector
"""


VERBS = ["NastaliqConnections", "FinalSelection"]


def load_rules(trypath, glyphlist, full=False):
    rules = {}
    with open(trypath) as csvfile:
        reader = csv.DictReader(csvfile)
        for line in reader:
            left_glyph = line["Left Glyph"]
            if not left_glyph in glyphlist:
                continue
            remainder = list(line.items())[1:]
            for (g, v) in remainder:
                old = g + "1"
                if old not in glyphlist:
                    continue
                if not full and (v == "1" or v == 1 or not v):
                    continue
                replacement = g + str(v)
                if not replacement in glyphlist:
                    warnings.warn(
                        f"{left_glyph}->{old} goes to {replacement} which does not exist"
                    )
                    continue
                if not old in rules:
                    rules[old] = {}
                if not replacement in rules[old]:
                    rules[old][replacement] = []
                rules[old][replacement].append(left_glyph)
                # if "KAF" in left_glyph:
                #    left_glyph2 = "G" + left_glyph[1:]
                #    rules[old][replacement].append(left_glyph2)

    if full:
        # Raised tooth manual rules
        rules["BEm1"]["BEmsd3"] = ["AINm1", "AINf1"]+ [x for x in glyphlist if "AINm" in x]
        rules["BEm1"]["BEmsd12"] = ["BEf1", "TEf1"] + [x for x in glyphlist if "BEm" in x or "TEm" in x]
        rules["BEm1"]["BEmsd10"] = ["SADf1", "TOEf1"] + [x for x in glyphlist if "SADm" in x or "TOEm" in x]
        rules["BEm1"]["BEmsd4"] = ["FEf1"] + [x for x in glyphlist if "FEm" in x]
        rules["BEm1"]["BEmsd15"] = ["QAFf1", "VAOf1"]

        if "TEm1" in glyphlist:
            rules["TEm1"]["TEmsd3"] = ["AINm1", "AINf1"]+ [x for x in glyphlist if "AINm" in x]
            rules["TEm1"]["TEmsd12"] = ["BEf1", "TEf1"] + [x for x in glyphlist if "BEm" in x or "TEm" in x]
            rules["TEm1"]["TEmsd10"] = ["SADf1", "TOEf1"] + [x for x in glyphlist if "SADm" in x or "TOEm" in x]
            rules["TEm1"]["TEmsd4"] = ["FEf1"] + [x for x in glyphlist if "FEm" in x]
            rules["TEm1"]["TEmsd15"] = ["QAFf1", "VAOf1"]
    return rules


class NastaliqConnections(FEZVerb):
    def action(self, args):
        parser = self.parser
        filename = args[0].value[1:-1]
        fixed_glyphs = []
        if len(args) == 2:
            fixed_glyphs = args[1].resolve(parser.fontfeatures, parser.font)
        rules = {}
        reachable = set([])
        basedir = os.path.dirname(parser.current_file)
        trypath = os.path.join(basedir, filename)

        if not os.path.exists(trypath):
            trypath = filename
            if not os.path.exists(trypath):
                raise ValueError("Couldn't find connections file %s" % trypath)

        rules = load_rules(trypath, parser.font.exportedGlyphs())

        r = fontFeatures.Routine(name="connections", flags=0x8)
        for oldglyph in rules:
            if oldglyph not in parser.font.exportedGlyphs():
                continue
            for replacement in rules[oldglyph]:
                context = rules[oldglyph][replacement]

                reachable |= set(context)
                reachable |= set([oldglyph, replacement])
                # To make this routine re-runnable we need to
                # find all the left glyphs, not just [mi]1 etc.
                stem = re.sub(r"(sd)?\d+$", "", oldglyph)
                oldglyphs = [
                     g
                     for g in parser.font.exportedGlyphs()
                     if g.startswith(stem) and g not in fixed_glyphs
                ]
                r.addRule(
                    fontFeatures.Substitution(
                        [oldglyphs],
                        [[replacement]],
                        postcontext=[context],
                        reverse=True,
                    )
                )
        parser.fontfeatures.namedClasses["reachable_glyphs"] = tuple(sorted(reachable))

        return [r]

class FinalSelection(FEZVerb):
    def action(self, args):
        parser = self.parser
        filename = args[0].value[1:-1]
        basedir = os.path.dirname(parser.current_file)
        trypath = os.path.join(basedir, filename)
        out_glyphs = args[1].resolve(parser.fontfeatures, parser.font)

        if not os.path.exists(trypath):
            trypath = filename
            if not os.path.exists(trypath):
                raise ValueError("Couldn't find connections file %s" % trypath)

        rules = []
        replacements = {}
        with open(trypath) as csvfile:
            reader = csv.DictReader(csvfile)
            for line in reader:
                left_glyph = line["Left Glyph"]
                if left_glyph not in out_glyphs:
                    continue
                remainder = list(line.items())[1:]
                prefix = [head+"1" for (head, cond) in remainder if cond != "1"]
                rules.append(fontFeatures.Substitution(
                        [[re.sub(r"(sd)?\d+$","1", left_glyph)]],
                        [[left_glyph]],
                        precontext=[prefix]))
        return rules
