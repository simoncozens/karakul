import fontFeatures
from glyphtools import get_glyph_metrics
import warnings


GRAMMAR = """
SpaceEater_Args = ws-> (,)
"""
VERBS = ["SpaceEater"]

accuracy1 = 8

class SeparateConsecutive:
    @classmethod
    def action(cls, parser):
    		classes = parser.fontfeatures.namedClasses
        if "inits" not in classes:
            raise ValueError("Needs @inits class defined")
        if "medis" not in classes:
            raise ValueError("Needs @medis class defined")
        if "finas" not in classes:
            raise ValueError("Needs @finas class defined")
        if "isols" not in classes:
            raise ValueError("Needs @isols class defined")

        finas_isols = classes["finas"] + classes["isols"]
        spacewidth = get_glyph_metrics(parser.font, "space")["width"]

        binned_medis = bin_glyphs_by_metric(
          parser.font, classes["medis"], "rise", bincount=accuracy1
        )

    @classmethod
    def lowest_point_after_entry(cls, font, glyph):
        paths1 = glyphs.beziers(font, glyph1)
        paths2 = glyphs.beziers(font, glyph2)
    elif glyphs.isbeziers(font):
        paths1 = FontParts.fromFontpartsGlyph(font[glyph1])
        paths2 = FontParts.fromFontpartsGlyph(font[glyph2])
    else:
        paths1 = BezierPath.fromFonttoolsGlyph(font, glyph1)
        paths2 = BezierPath.fromFonttoolsGlyph(font, glyph2)
