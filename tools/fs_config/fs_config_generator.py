#!/usr/bin/env python
"""

This script is used for generating configuration files for configuring
Android filesystem properties. Internally, its composed of a plug-able
interface to support the understanding of new input and output parameters.

Run the help for a list of supported plugins and their capabilities.

Further documentation can be found in the README.
"""

import argparse
import ConfigParser
import re


# Lowercase generator used to be inline with @staticmethod.
class generator(object):
    '''Used as a decorator to classes to add them to
    the internal plugin interface. Plugins added
    with @generator() are automatically added to
    the command line.

    For instance, to add a new generator
    called foo and have it added just do this:

        @generator("foo")
        class FooGen(object):
            ...
    '''
    _generators = {}

    def __init__(self, gen):
        '''
        Args:
            gen (str): The name of the generator to add.

        Raises:
            Exception: If their is a similarly named generator already added.

        '''
        self._gen = gen

        if gen in generator._generators:
            raise Exception('Duplicate generator name' + gen)

        generator._generators[gen] = None

    def __call__(self, cls):

        generator._generators[self._gen] = cls()
        return cls

    @staticmethod
    def get():
        '''
        Returns the list of registered generators.
        '''
        return generator._generators


class Utils(object):
    '''
    Various assorted static utilities.
    '''

    @staticmethod
    def convert_int(num):
        '''
        Converts a string to an int for various bases.

        Args:
            num (str): The string to convert to an int.

        Returns:
            The integer value or None if it cannot bet converted.
        '''

        try:
            if num.startswith('0x'):
                return int(num, 16)
            elif num.startswith('0b'):
                return int(num, 2)
            elif num.startswith('0'):
                return int(num, 8)
            else:
                return int(num, 10)
        except ValueError:
            pass
        return None

    @staticmethod
    def in_range(value, ranges):
        '''
        Tests if a value is in a given range.

        Args:
            value (int): The value to test.
            range ((int, int)): The range to test value within.

        Returns:
            True if value is within range, false otherwise.
        '''

        return any(lower <= value <= upper for (lower, upper) in ranges)


class AID(object):
    '''
    This class represents an Android ID or an AID.

    Attributes:
        identifier (str): The identifier name for a #define.
        value (str) The User Id (uid) of the associate define.
        found (str) The file it was found in, can be None.
        normalized_value (str): Same as value, but base 10.
        friendly (str): The friendly name of aid.

    '''

    PREFIX = 'AID_'

    def __init__(self, identifier, value, normalized_value=None, found=None):
        '''
        Args:
            identifier: The identifier name for a #define <identifier>.
            value: The value of the AID, aka the uid.
                normalized_value (str): The normalized base10 value of value,
                if not specified it is generated.
              found (str): The file found in, not required to be specified.

        Raises:
            ValueError: if value cannot be normalized via int() and
                normalzed_value is unspecified.
        '''
        self.identifier = identifier
        self.value = value
        self.found = found
        self.normalized_value = normalized_value if normalized_value else str(
            int(value))

        # Where we calculate the friendly name
        self.friendly = identifier[len(AID.PREFIX):].lower()


class FSConfig(object):
    '''
    Represents a file system configuration entry for specifying
    file system capabilities.

    Attributes"
        mode (str): The mode of the file or directory.
        user (str): The uid or #define identifier (AID_SYSTEM)
        group (str): The gid or #define identifier (AID_SYSTEM)
        caps (str): The capability set.
        filename (str): The file it was found in.
    '''

    def __init__(self, mode, user, group, caps, path, filename):
        '''
        Args:
            mode (str): The mode of the file or directory.
            user (str): The uid or #define identifier (AID_SYSTEM)
            group (str): The gid or #define identifier (AID_SYSTEM)
            caps (str): The capability set as a list.
            filename (str): The file it was found in.
        '''
        self.mode = mode
        self.user = user
        self.group = group
        self.caps = caps
        self.path = path
        self.filename = filename


class AIDHeaderParser(object):
    '''
    Parses a C header file and extracts lines starting with #define AID_<name>
    It provides some basic sanity checks. The information extracted from this
    file can later be used to sanity check other things (like oem ranges) as
    well as generating a mapping of names to uids. It was primarily designed to
    parse the private/android_filesystem_config.h, but any C header should
    work.
    '''

    _SKIPWORDS = ['UNUSED']
    _AID_DEFINE = re.compile('\s*#define\s+%s.*' % AID.PREFIX)
    _OEM_START_KW = 'START'
    _OEM_END_KW = 'END'
    _OEM_RANGE = re.compile('AID_OEM_RESERVED_[0-9]*_{0,1}(%s|%s)' %
                            (_OEM_START_KW, _OEM_END_KW))

    # Some of the AIDS like AID_MEDIA_EX had names like mediaex
    # list a map of things to fixup until we can correct these
    # at a later data
    _FIXUPS = {
        'media_drm': 'mediadrm',
        'media_ex': 'mediaex',
        'media_codec': 'mediacodec'
    }

    def __init__(self, aid_header):
        '''
        Args:
            aid_header (str): file name for the header
                file containing AID entries.
        '''
        self._aid_header = aid_header
        self._aid_name_to_value = {}
        self._aid_value_to_name = {}
        self._oem_ranges = {}

        with open(aid_header) as open_file:
            self._parse(open_file)

        self._process_and_check()

    def _parse(self, aid_file):
        '''
        Parses an AID header file. Internal use only.

        Args:
            aid_file (file): The open AID header file to parse.

        Raise:
            Exception: With message set to indicate the error.
        '''

        lineno = 0

        for line in aid_file:
            lineno = lineno + 1

            errmsg = ('Error "%s" in file: "' + self._aid_header + '" on line: '
                      + str(lineno))

            if AIDHeaderParser._AID_DEFINE.match(line):
                chunks = line.split()

                if any(x in chunks[1] for x in AIDHeaderParser._SKIPWORDS):
                    continue

                orig = chunks[1]
                value = Utils.convert_int(chunks[2])
                if value == None:
                    raise Exception(errmsg %
                                    ('Invalid aid value aid "%s"' % chunks[2]))

                if AIDHeaderParser._is_oem_range(orig):
                    try:
                        self._handle_oem_range(orig, value)
                    except Exception as exception:
                        raise Exception(errmsg %
                                        (str(exception) + ' for "%s"' % orig))

                    continue

                try:
                    self._handle_aid(orig, value)
                except Exception as exception:
                    raise Exception(errmsg %
                                    (str(exception) + ' for "%s"' % orig))

    def _handle_aid(self, identifier, value):
        '''
        Handles an AID, sanity checking, generating the friendly name and
        adding it to the internal maps. Internal use only.

        Args:
            identifier (str): The name of the #define identifier. ie AID_FOO.
            value (int): The value associated with the identifier.

        Raise:
            Exception: With message set to indicate the error.
        '''

        aid = AID(identifier, value)

        # Fixup the generated friendly name to our fixup list
        aid.friendly = AIDHeaderParser._fixup_friendly(aid.friendly)

        # duplicate name
        if aid.friendly in self._aid_name_to_value:
            raise Exception('Duplicate aid "%s"' % identifier)

        if value in self._aid_value_to_name:
            raise Exception('Duplicate aid value "%u" for %s' % value,
                            identifier)

        self._aid_name_to_value[aid.friendly] = aid
        self._aid_value_to_name[value] = aid.friendly

    def _handle_oem_range(self, identifier, value):
        '''
        When encountering special AID defines, notably for the OEM ranges
        this method handles sanity checking and adding them to the internal
        maps. For internal use only.

        Args:
            identifier (str): The name of the #define identifier.
                ie AID_OEM_RESERVED_START/END.
            value (int): The value associated with the identifier.

        Raise:
            Exception: With message set to indicate the error.
        '''

        # convert AID_OEM_RESERVED_START or AID_OEM_RESERVED_<num>_START
        # to AID_OEM_RESERVED or AID_OEM_RESERVED_<num>
        is_start = identifier.endswith(AIDHeaderParser._OEM_START_KW)

        tostrip = len(AIDHeaderParser._OEM_START_KW) if is_start \
                    else len(AIDHeaderParser._OEM_END_KW)

        # ending _
        tostrip = tostrip + 1

        strip = identifier[:-tostrip]
        if strip not in self._oem_ranges:
            self._oem_ranges[strip] = []

        if len(self._oem_ranges[strip]) > 2:
            raise Exception('Too many same OEM Ranges "%s"' % identifier)

        if len(self._oem_ranges[strip]) == 1:
            tmp = self._oem_ranges[strip][0]

            if tmp == value:
                raise Exception('START and END values equal %u' % value)
            elif is_start and tmp < value:
                raise Exception('END value %u less than START value %u' %
                                (tmp, value))
            elif not is_start and tmp > value:
                raise Exception('END value %u less than START value %u' %
                                (value, tmp))

        self._oem_ranges[strip].append(value)

    def _process_and_check(self):
        '''
        After parsing and generating the internal data structures, this method
        is responsible for sanity checking ALL of the acquired data.

        Raise:
            Exception: With the message set to indicate the specific error.
        '''

        # tuplefy the lists since we don'range2 want them mutable
        self._oem_ranges = [
            AIDHeaderParser._convert_lst_to_tup(k, v)
            for k, v in self._oem_ranges.iteritems()
        ]

        # Check for overlapping ranges
        for range1 in self._oem_ranges:
            for range2 in self._oem_ranges:
                if range1 != range2 and AIDHeaderParser._get_overlap(range1,
                                                                     range2):
                    raise Exception("Overlapping OEM Ranges found %s and %s" %
                                    (str(range1), str(range2)))

        # No aids should be in OEM range1
        for aid in self._aid_value_to_name:

            if Utils.in_range(aid, self._oem_ranges):
                name = self._aid_value_to_name[aid]
                raise Exception(
                    'AID "%s" value: %u within reserved OEM Range: "%s"' %
                    (name, aid, str(self._oem_ranges)))

    def get_oem_ranges(self):
        '''
        Retrieves the OEM ranges as a list of tuples.
        [ (0, 42), (50, 105) ... ]

        Returns:
            A list of range tuples.
        '''
        return self._oem_ranges

    def get_aids(self):
        '''
        Retrieves the list of found AIDs

        Returns:
            A list of AID() objects.
        '''
        return self._aid_name_to_value

    @staticmethod
    def _convert_lst_to_tup(name, lst):
        '''
        Converts a mutable list to a non-mutable tuple.
        Used ONLY for ranges and thus enforces a length
        of 2.

        Args:
            lst (List): list that should be "tuplefied".

        Returns:
            Tuple(lst)
        '''
        if not lst or len(lst) != 2:
            raise Exception('Mismatched range for "%s"' % name)

        return tuple(lst)

    @staticmethod
    def _fixup_friendly(friendly):
        '''
        Fixup any friendly mappings that don't follow
        the convention in the AID class.

        Args:
            friendly (str): The friendly name.

        Returns:
            The fixedup friendly name as a str.
        '''

        if friendly in AIDHeaderParser._FIXUPS:
            return AIDHeaderParser._FIXUPS[friendly]

        return friendly

    @staticmethod
    def _is_oem_range(aid):
        '''
        Detects if a given aid is within the reserved OEM range.

        Args:
            aid (int): The aid to test

        Returns:
            True if it is within the range, False otherwise.
        '''

        return AIDHeaderParser._OEM_RANGE.match(aid)

    @staticmethod
    def _get_overlap(range_a, range_b):
        '''
        Calculates the overlap of two range tuples.

        Args:
            range_a: The first tuple range eg (0, 5).
            range_b: The second tuple range eg (3, 7).

        Returns:
            The delta of of the overlap, 0 means no overlap.
        '''

        return max(0, min(range_a[1], range_b[1]) - max(range_a[0], range_b[0]))


class FSConfigFileParser(object):
    '''
    This class is responsible for parsing the config.fs ini format files.
    It collects and checks all the data in these files and makes it available
    for consumption post processed.
    '''

    # These _AID vars work together to ensure that an AID section name
    # cannot contain invalid characters for a C define or a passwd/group file.
    # Since _AID_PREFIX is within the set of _AID_MATCH the error logic only
    # checks end, if you change this, you may have to update the error
    # detection code.
    _AID_MATCH = re.compile('%s[A-Z0-9_]+' % AID.PREFIX)
    _AID_ERR_MSG = 'Expecting upper case, a number or underscore'

    # list of handler to required options, used to identify the
    # parsing section
    _SECTIONS = [
        ('_handle_aid', ('value',)), ('_handle_path',
                                      ('mode', 'user', 'group', 'caps'))
    ]

    def __init__(self, config_files, oem_ranges):
        '''
        Args:
            config_files ([str]): The list of config.fs files to parse.
                Note the filename is not important.
            oem_ranges ([(),()]): range tuples indicating reserved OEM ranges.
        '''

        self._files = []
        self._dirs = []
        self._aids = []

        self._seen_paths = {}
        # (name to file, value to aid)
        self._seen_aids = ({}, {})

        self._oem_ranges = oem_ranges

        self._config_files = config_files

        for config_file in self._config_files:
            self._parse(config_file)

    def _parse(self, file_name):
        '''
        Parses and verifies config.fs files. Internal use only.

        Args:
            The config.fs (PythonConfigParser file format) file to parse

        Raises:
            Exception: On any parsing error with a message set.
            Anything raised by ConfigParser.read()
        '''

        # Separate config parsers for each file found. If you use
        # read(filenames...) later files can override earlier files which is
        # not what we want. Track state across files and enforce with
        # _handle_dup(). Note, strict ConfigParser is set to true in
        # Python >= 3.2, so in previous versions same file sections can
        # override previous
        # sections.

        config = ConfigParser.ConfigParser()
        config.read(file_name)

        for section in config.sections():

            found = False

            for test in FSConfigFileParser._SECTIONS:
                handler = test[0]
                options = test[1]

                if all([config.has_option(section, item) for item in options]):
                    handler = getattr(self, handler)
                    handler(file_name, section, config)
                    found = True
                    break

            if not found:
                raise Exception('Invalid section "%s" in file: "%s"' %
                                (section, file_name))

            # sort entries:
            # * specified path before prefix match
            # ** ie foo before f*
            # * lexicographical less than before other
            # ** ie boo before foo
            # Given these paths:
            # paths=['ac', 'a', 'acd', 'an', 'a*', 'aa', 'ac*']
            # The sort order would be:
            # paths=['a', 'aa', 'ac', 'acd', 'an', 'ac*', 'a*']
            # Thus the fs_config tools will match on specified paths before
            # attempting prefix, and match on the longest matching prefix.
            self._files.sort(
                key=lambda item: FSConfigFileParser._file_key(item))

            # sort on value of (file_name, name, value, strvalue)
            # This is only cosmetic so AIDS are arranged in ascending order
            # within the generated file.
            self._aids.sort(key=lambda item: item.normalized_value)

    def _handle_aid(self, file_name, section_name, config):
        '''
        Verifies an AID entry and adds it to the aid list. Internal use only.

        Raises:
          Exception: On any parsing error with aid message set.
        '''

        FSConfigFileParser._handle_dup_and_add('AID', file_name, section_name,
                                               self._seen_aids[0])

        errmsg = ('%s for: \"' + section_name + '" file: \"' + file_name + '\"')

        match = FSConfigFileParser._AID_MATCH.match(section_name)
        invalid = match.end() if match else len(AID.PREFIX)
        if invalid != len(section_name):
            tmp_errmsg = ('Invalid characters in AID section at "%d" for: "%s"'
                          % (invalid, FSConfigFileParser._AID_ERR_MSG))
            raise Exception(errmsg % tmp_errmsg)

        value = config.get(section_name, 'value')

        if not value:
            raise Exception(errmsg % 'Found specified but unset "value"')

        normalized_value = Utils.convert_int(value)
        if not normalized_value:
            raise Exception(errmsg % (
                'Invalid "value", not aid number, got: \"%s\"' % value))

        # Values must be within OEM range
        if not any(lower <= normalized_value <= upper
                   for (lower, upper) in self._oem_ranges):
            emsg = '"value" not in valid range %s, got: %s'
            emsg = emsg % (str(self._oem_ranges), value)
            raise Exception(errmsg % emsg)

        # use the normalized int value in the dict and detect
        # duplicate definitions of the same vallue
        normalized_value = str(normalized_value)
        FSConfigFileParser._handle_dup_and_add(
            'AID', file_name, normalized_value, self._seen_aids[1])

        # Append aid tuple of (AID_*, base10(value), _path(value))
        # We keep the _path version of value so we can print that out in the
        # generated header so investigating parties can identify parts.
        # We store the base10 value for sorting, so everything is ascending
        # later.
        self._aids.append(AID(section_name, value, normalized_value, file_name))

    def _handle_path(self, file_name, section_name, config):
        '''
        Handles a file capability entry, verifies it, and adds it to
        to the internal dirs or files list based on path. If it ends
        with a / its a dir. Internal use only.

        Args:
            file_name (str): The current name of the file being parsed.
            section_name (str): The name of the section to parse.
            config (str): The config parser.

        Raises:
            Exception: On any validation error with message set.
        '''

        FSConfigFileParser._handle_dup_and_add('path', file_name, section_name,
                                               self._seen_paths)

        mode = config.get(section_name, 'mode')
        user = config.get(section_name, 'user')
        group = config.get(section_name, 'group')
        caps = config.get(section_name, 'caps')

        errmsg = ('Found specified but unset option: \"%s" in file: \"' +
                  file_name + '\"')

        if not mode:
            raise Exception(errmsg % 'mode')

        if not user:
            raise Exception(errmsg % 'user')

        if not group:
            raise Exception(errmsg % 'group')

        if not caps:
            raise Exception(errmsg % 'caps')

        caps = caps.split()

        tmp = []
        for cap in caps:
            if Utils.convert_int(cap):
                tmp.append('(' + cap + ')')
            else:
                tmp.append('(1ULL << CAP_' + cap.upper() + ')')

        caps = tmp

        if len(mode) == 3:
            mode = '0' + mode

        try:
            int(mode, 8)
        except:
            raise Exception('Mode must be octal characters, got: "' + mode +
                            '"')

        if len(mode) != 4:
            raise Exception('Mode must be 3 or 4 characters, got: "' + mode +
                            '"')

        caps = '|'.join(caps)

        entry = FSConfig(mode, user, group, caps, section_name, file_name)
        if section_name[-1] == '/':
            self._dirs.append(entry)
        else:
            self._files.append(entry)

    def get_files(self):
        '''
        Returns:
             a list of FSConfig() objects for file paths.
        '''
        return self._files

    def get_dirs(self):
        '''
        Returns:
            a list of FSConfig() objects for directory paths.
        '''
        return self._dirs

    def get_aids(self):
        '''
        Returns:
            a list of AID() objects.
        '''
        return self._aids

    @staticmethod
    def _file_key(fs_config):
        '''
        This is used as a the function to the key parameter of a sort.
        it wraps the string supplied in a class that implements the
        appropriate __lt__ operator for the sort on path strings. See
        StringWrapper class for more details.

        Args:
            fs_config (FSConfig): A FSConfig entry.

        Returns:
            A StringWrapper object
        '''

        # Wrapper class for custom prefix matching strings
        class StringWrapper(object):
            '''
            Wrapper class used for sorting prefix strings

            The algorithm is as follows:
              - specified path before prefix match
                - ie foo before f*
              - lexicographical less than before other
                - ie boo before foo

            Given these paths:
            paths=['ac', 'a', 'acd', 'an', 'a*', 'aa', 'ac*']
            The sort order would be:
            paths=['a', 'aa', 'ac', 'acd', 'an', 'ac*', 'a*']
            Thus the fs_config tools will match on specified paths before
            attempting prefix, and match on the longest matching prefix.
            '''

            def __init__(self, path):
                '''
                Args:
                    path (str): the path string to wrap.
                '''
                self._orig = path
                self._is_prefix = path[-1] == '*'
                if self._is_prefix:
                    self._path = path[:-1]
                else:
                    self._path = path

            def __lt__(self, other):

                # if were both suffixed the smallest string
                # is 'bigger'
                if self._is_prefix and other._is_prefix:
                    result = len(self._path) > len(other._path)
                # If I am an the suffix match, im bigger
                elif self._is_prefix:
                    result = False
                # If other is the suffix match, he's bigger
                elif other._is_prefix:
                    result = True
                # Alphabetical
                else:
                    result = self._path < other._path
                return result

        return StringWrapper(fs_config.path)

    @staticmethod
    def _handle_dup_and_add(name, file_name, section_name, seen):
        '''
        Tracks and detects duplicates, Internal use only.

        Args:
            name (str): The name to use in the error reporting. The pretty
                name for the section.
            file_name (str): The file currently being parsed.
            section_name (str): The name of the section. This would be path
                or identifier depending on what's being parsed.
            seen (dict): The dictionary of seen things to check against.

        Raises:
            Exception: With an appropriate message set.
        '''
        if section_name in seen:
            dups = '"' + seen[section_name] + '" and '
            dups += file_name
            raise Exception('Duplicate ' + name + ' "' + section_name +
                            '" found in files: ' + dups)

        seen[section_name] = file_name


class BaseGenerator(object):
    '''
    Base class for generators, generators should implement
    these method stubs.
    '''

    def add_opts(self, opt_group):
        '''
        Used to add per-generator options to the command line.

        Args:
            opt_group (argument group object): The argument group to append to.
                See the ArgParse docs for more details.
        '''

        raise Exception("Not Implemented")

    def __call__(self, args):
        '''
        This is called to do whatever magic the generator does.

        Args:
            args (Dict()): The arguments from ArgParse as a dictionary.
                ie if you specified an argument of foo in add_opts, access
                it via args['foo']
        '''

        raise Exception("Not Implemented")


@generator("fsconfig")
class FSConfigGen(BaseGenerator):
    '''
    Generates the android_filesystem_config.h file to be used in generating
    fs_config_files and fs_config_dirs.
    '''

    _GENERATED = '''
/*
 * THIS IS AN AUTOGENERATED FILE! DO NOT MODIFY
 */
 '''

    _INCLUDES = ['<private/android_filesystem_config.h>', 'generated_oem_aid.h']

    _DEFINE_NO_DIRS = '#define NO_ANDROID_FILESYSTEM_CONFIG_DEVICE_DIRS\n'
    _DEFINE_NO_FILES = '#define NO_ANDROID_FILESYSTEM_CONFIG_DEVICE_FILES\n'

    _DEFAULT_WARNING = (
        '#warning No device-supplied android_filesystem_config.h,'
        ' using empty default.')

    _NO_ANDROID_FILESYSTEM_CONFIG_DEVICE_DIRS_ENTRY = (
        '{ 00000, AID_ROOT, AID_ROOT, 0,'
        '"system/etc/fs_config_dirs" },')

    _NO_ANDROID_FILESYSTEM_CONFIG_DEVICE_FILES_ENTRY = (
        '{ 00000, AID_ROOT, AID_ROOT, 0,'
        '"system/etc/fs_config_files" },')

    _IFDEF_ANDROID_FILESYSTEM_CONFIG_DEVICE_DIRS = (
        '#ifdef NO_ANDROID_FILESYSTEM_CONFIG_DEVICE_DIRS')

    _ENDIF = '#endif'

    _OPEN_FILE_STRUCT = (
        'static const struct fs_path_config android_device_files[] = {')

    _OPEN_DIR_STRUCT = (
        'static const struct fs_path_config android_device_dirs[] = {')

    _CLOSE_FILE_STRUCT = '};'

    _GENERIC_DEFINE = "#define %s\t%s"

    _FILE_COMMENT = '// Defined in file: \"%s\"'

    def add_opts(self, opt_group):

        opt_group.add_argument('fsconfig',
                               nargs='+',
                               help='The list of fsconfig files to parse')

        opt_group.add_argument('--aidhdr',
                               required=True,
                               help='An android_filesystem_config.h file'
                               'to parse AIDs and OEM Ranges from')

    def __call__(self, args):

        # If supplied, parse the header file for OEM Ranges
        oem_ranges = None
        if 'aidhdr' in args and args['aidhdr']:
            hdr = AIDHeaderParser(args['aidhdr'])
            oem_ranges = hdr.get_oem_ranges()

        parser = FSConfigFileParser(args['fsconfig'], oem_ranges)
        FSConfigGen._generate(parser.get_files(), parser.get_dirs(),
                              parser.get_aids())

    @staticmethod
    def _to_fs_entry(fs_config):
        '''
        Given an FSConfig entry, converts it to a proper
        array entry for the array entry.

        { mode, user, group, caps, "path" },

        Args:
            fs_config (FSConfig): The entry to convert to
                a valid C array entry.
        '''

        # Get some short names
        mode = fs_config.mode
        user = fs_config.user
        group = fs_config.group
        fname = fs_config.filename
        caps = fs_config.caps
        path = fs_config.path

        fmt = '{ %s, %s, %s, %s, "%s" },'

        expanded = fmt % (mode, user, group, caps, path)

        print FSConfigGen._FILE_COMMENT % fname
        print '    ' + expanded

    @staticmethod
    def _gen_inc():
        '''
        Generate the include header lines and print to stdout.
        Internal use only.
        '''
        for i in FSConfigGen._INCLUDES:
            tmp = '#include %s' if i.startswith('<') else '#include "%s"'
            print tmp % i

    @staticmethod
    def _generate(files, dirs, aids):
        '''
        Generates a valid OEM android_filesystem_config.h header file to
        stdout.

        Args:
            files ([FSConfig]): A list of FSConfig objects for file entries.
            dirs ([FSConfig]): A list of FSConfig objects for directory
                entries.
            aids ([AIDS]): A list of AID objects for Android Id entries.
        '''
        print FSConfigGen._GENERATED
        print

        FSConfigGen._gen_inc()
        print

        are_dirs = len(dirs) > 0
        are_files = len(files) > 0
        are_aids = len(aids) > 0

        if are_aids:
            for aid in aids:
                # use the preserved _path value
                print FSConfigGen._FILE_COMMENT % aid.found
                print FSConfigGen._GENERIC_DEFINE % (aid.identifier, aid.value)

            print

        if not are_dirs:
            print FSConfigGen._DEFINE_NO_DIRS

        if not are_files:
            print FSConfigGen._DEFINE_NO_FILES

        if not are_files and not are_dirs and not are_aids:
            print FSConfigGen._DEFAULT_WARNING
            return

        if are_files:
            print FSConfigGen._OPEN_FILE_STRUCT
            for fs_config in files:
                FSConfigGen._to_fs_entry(fs_config)

            if not are_dirs:
                print FSConfigGen._IFDEF_ANDROID_FILESYSTEM_CONFIG_DEVICE_DIRS
                print(
                    '    ' +
                    FSConfigGen._NO_ANDROID_FILESYSTEM_CONFIG_DEVICE_DIRS_ENTRY)
                print FSConfigGen._ENDIF
            print FSConfigGen._CLOSE_FILE_STRUCT

        if are_dirs:
            print FSConfigGen._OPEN_DIR_STRUCT
            for dir_entry in dirs:
                FSConfigGen._to_fs_entry(dir_entry)

            print FSConfigGen._CLOSE_FILE_STRUCT


@generator("aidarray")
class AIDArrayGen(BaseGenerator):
    '''
    Generates the android_id static array.
    '''

    _GENERATED = ('/*\n'
                  ' * THIS IS AN AUTOGENERATED FILE! DO NOT MODIFY!\n'
                  '*/')

    _INCLUDE = '#include <private/android_filesystem_config.h>'

    _STRUCT_FS_CONFIG = ('struct android_id_info {\n'
                         '    const char *name;\n'
                         '    unsigned aid;\n'
                         '};')

    _OPEN_ID_ARRAY = 'static const struct android_id_info android_ids[] = {'

    _ID_ENTRY = '    { "%s", %s },'

    _CLOSE_FILE_STRUCT = '};'

    _COUNT = ('#define android_id_count \\\n'
              '    (sizeof(android_ids) / sizeof(android_ids[0]))')

    def add_opts(self, opt_group):

        opt_group.add_argument('hdrfile',
                               help='The android_filesystem_config.h'
                               'file to parse')

    def __call__(self, args):

        hdr = AIDHeaderParser(args['hdrfile'])

        print AIDArrayGen._GENERATED
        print
        print AIDArrayGen._INCLUDE
        print
        print AIDArrayGen._STRUCT_FS_CONFIG
        print
        print AIDArrayGen._OPEN_ID_ARRAY

        for name, aid in hdr.get_aids().iteritems():
            print AIDArrayGen._ID_ENTRY % (name, aid.identifier)

        print AIDArrayGen._CLOSE_FILE_STRUCT
        print
        print AIDArrayGen._COUNT
        print


@generator("oemaid")
class OEMAidGen(BaseGenerator):
    '''
    Generates the OEM AID_<name> value header file.
    '''

    _GENERATED = ('/*\n'
                  ' * THIS IS AN AUTOGENERATED FILE! DO NOT MODIFY!\n'
                  '*/')

    _GENERIC_DEFINE = "#define %s\t%s"

    _FILE_COMMENT = '// Defined in file: \"%s\"'

    def __init__(self):

        self._old_file = None

    def add_opts(self, opt_group):

        opt_group.add_argument('fsconfig',
                               nargs='+',
                               help='The list of fsconfig files to parse')

        opt_group.add_argument('--aidhdr',
                               required=True,
                               help='An android_filesystem_config.h file'
                               'to parse AIDs and OEM Ranges from')

    def __call__(self, args):

        hdr_parser = AIDHeaderParser(args['aidhdr'])

        parser = FSConfigFileParser(args['fsconfig'],
                                    hdr_parser.get_oem_ranges())

        aids = parser.get_aids()

        # nothing to do if no aids defined
        if len(aids) == 0:
            return

        print OEMAidGen._GENERATED

        for aid in aids:
            self._print_aid(aid)
            print

    def _print_aid(self, aid):
        '''
        Prints a valid #define AID identifier to stdout.
        Args:
            aid to print
        '''

        # print the source file location of the AID
        found_file = aid.found
        if found_file != self._old_file:
            print OEMAidGen._FILE_COMMENT % found_file
            self._old_file = found_file

        print OEMAidGen._GENERIC_DEFINE % (aid.identifier, aid.value)


@generator("passwd")
class PasswdGen(BaseGenerator):
    '''
    Generates the /etc/passwd file per man (5) passwd.
    '''

    _GENERATED = ('#\n' '# THIS IS AN AUTOGENERATED FILE! DO NOT MODIFY!\n' '#')

    _FILE_COMMENT = '# Defined in file: \"%s\"'

    def __init__(self):

        self._old_file = None

    def add_opts(self, opt_group):

        opt_group.add_argument('fsconfig',
                               nargs='*',
                               help='The list of fsconfig files to parse.')

        opt_group.add_argument('--aidhdr',
                               required=True,
                               help='An android_filesystem_config.h file'
                               'to parse AIDs and OEM Ranges from')

    def __call__(self, args):

        hdr_parser = AIDHeaderParser(args['aidhdr'])

        parser = FSConfigFileParser(args['fsconfig'],
                                    hdr_parser.get_oem_ranges())

        aids = parser.get_aids()

        # nothing to do if no aids defined
        if len(aids) == 0:
            return

        print PasswdGen._GENERATED

        for aid in aids:
            self._print_formatted_line(aid)

    def _print_formatted_line(self, aid):
        '''
        Prints the aid to stdout in the passwd format.
        Internal use only.

        Colon delimited:
            login name, friendly name
            encrypted password (optional)
            uid (int)
            gid (int)
            User name or comment field
            home directory
            interpreter (optional)

        Args:
            aid (AID): The aid to print.
        '''
        if self._old_file != aid.found:
            self._old_file = aid.found
            print PasswdGen._FILE_COMMENT % aid.found

        logon = aid.friendly
        uid = aid.normalized_value
        print "%s::%s:%s::/:/system/bin/sh" % (logon, uid, uid)


@generator("group")
class GroupGen(PasswdGen):
    '''
    Generates the /etc/group file per man (5) group.
    '''

    # Overrides parent
    def _print_formatted_line(self, aid):
        '''
        Prints the aid to stdout in the group format.
        Internal use only.

        Formatted (per man 5 group) like:
            group_name:password:GID:user_list

        Args:
            aid (AID): The aid to print.
        '''
        if self._old_file != aid.found:
            self._old_file = aid.found
            print PasswdGen._FILE_COMMENT % aid.found

        logon = aid.friendly
        uid = aid.normalized_value
        print "%s::%s:" % (logon, uid)


def main():
    '''
    main entry point for execution
    '''

    opt_parser = argparse.ArgumentParser(
        description='A tool for parsing fsconfig config files and producing' +
        'digestable outputs.')
    subparser = opt_parser.add_subparsers(help='generators')

    gens = generator.get()

    # for each gen, instantiate and add them as an option
    for name, gen in gens.iteritems():

        generator_option_parser = subparser.add_parser(name, help=gen.__doc__)
        generator_option_parser.set_defaults(which=name)

        opt_group = generator_option_parser.add_argument_group(name +
                                                               ' options')
        gen.add_opts(opt_group)

    args = opt_parser.parse_args()

    args_as_dict = vars(args)
    which = args_as_dict['which']
    del args_as_dict['which']

    gens[which](args_as_dict)


if __name__ == '__main__':
    main()
