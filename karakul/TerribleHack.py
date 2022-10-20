from fez import FEZVerb
PARSEOPTS = dict(use_helpers=True)

GRAMMAR = """
?start: action
action:
"""
import re
import json

db = None
VERBS = ["ATerribleHack"]

class ATerribleHack(FEZVerb):
    def action(self, args):
        self.parser.font.axes[0].min = 200
        self.parser.font.axes[0].default = 400
        self.parser.font.axes[0].max = 700
        for m in self.parser.font.masters:
            if m.location["wght"] == 10:
                m.location["wght"] = 200
            if m.location["wght"] == 100:
                m.location["wght"] = 400
            if m.location["wght"] == 734:
                m.location["wght"] = 700
        return []
