import fontFeatures
import re

from fez import FEZVerb

PARSEOPTS = dict(use_helpers=True)

GRAMMAR = """
?start: action
action: glyphselector+ "->" BARENAME
"""

VERBS = ["SuffixingSubstitute"]

class SuffixingSubstitute(FEZVerb):
    def action(self, args):
        parser = self.parser
        orig_inputs  = [g.resolve(parser.fontfeatures, parser.font) for g in args[:-1]]
        inputs = []
        suffix  = args[-1]
        outputs = []
        for place in orig_inputs:
            output = []
            this_input = []
            for g in place:
                replacement = re.sub(r'\w\d+$', suffix, g)
                if g not in self.parser.font.exportedGlyphs() or replacement not in self.parser.font.exportedGlyphs():
                    continue
                this_input.append(g)
                output.append(replacement)
            outputs.append(output)
            inputs.append(this_input)
        return [fontFeatures.Substitution(inputs, outputs)]
