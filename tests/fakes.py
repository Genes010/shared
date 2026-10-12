"""Nep-runner die vooraf ingestelde antwoorden geeft op basis van een sleutelwoord in het script."""

from smbconnect.runner import CommandResult, Runner


class FakeRunner(Runner):
    def __init__(self, responses):
        super().__init__()
        self.responses = responses  # lijst van (sleutelwoord, data)
        self.calls = []
        self.logged = []

    def log(self, kind, text):
        self.logged.append((kind, text))

    def ps_json(self, script, **kwargs):
        self.calls.append((script, kwargs))
        for key, data in self.responses:
            if key in script:
                return CommandResult("PS", 0, "", "", data)
        return CommandResult("PS", 1, "", "geen nep-antwoord", None)
