class general_parser:
    parser_types = ["Default", "PDF", "HTML", "JSON", "CSV"]

    def __init__(self):
        self.type = "Default"

    def set_type(self, type):
        if type in self.parser_types:
            self.type = type
        else:
            raise ValueError(
                f"Invalid parser type: {type}. Available types are: {self.parser_types}"
            )
