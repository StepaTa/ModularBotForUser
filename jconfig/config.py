import json

class Jconfig:
    def __init__(self, file, separator='/'):
        self.separator = separator
        self.file = file
        self.config = json.load(open(self.file))
        self.config_from_path = self.config
        self.edit_config = self.config

    def get(self, path):
        """ get config property """

        value = ''
        for part in path.split(self.separator):
            value = self.config_from_path[part]
            self.config_from_path = value
        
        self.config_from_path = self.config
        return value
        
    def set(self, path, value):
        """ set config property """

        parts = path.split(self.separator)
        rev_parts = list(reversed(parts))
        data = {}
        for index, _ in enumerate(rev_parts):
            try:
                current_path = self.separator.join(parts[: - (index + 1)])
                obj = self.get(current_path)
                prop = parts[- (index + 1)]
                prop = int(prop) if self.int_property(prop) else prop
                if index == 0:
                    obj[prop] = value
                else:
                    obj[prop] = obj[prop]
                data = obj

            except KeyError:
                break

        self.config[parts[0]] = data
        self.commit()

    def commit(self):
        """ rewrites the json config file after changes """

        json.dump(self.config, open(self.file, 'w'))
    
    def setSeparator(self, separator):
        """ resets the separator used to query the configs """

        self.separator = separator
    
    def int_property(self, prop):
        """ returns True if the prop is a value of type int """
        
        try:
            int_prop = int(prop)
            if type(int_prop) == int:
                return True
        except ValueError:
            return False