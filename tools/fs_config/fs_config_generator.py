#!/usr/bin/env python
"""Generates config files for Android file system properties.

This script is used for generating configuration files for configuring
Android filesystem properties. Internally, its composed of a plug-able
interface to support the understanding of new input and output parameters.

Run the help for a list of supported plugins and their capabilities.

Further documentation can be found in the README.
"""

import argparse
import ConfigParser
import re
import sys
import textwrap

# Keep the tool in one file to make it easy to run.
# pylint: disable=too-many-lines


# Lowercase generator used to be inline with @staticmethod.
class generator(object):  # pylint: disable=invalid-name
    """A decorator class to add commandlet plugins.

    Used as a decorator to classes to add them to
    the internal plugin interface. Plugins added
    with @generator() are automatically added to
    the command line.

    For instance, to add a new generator
    called foo and have it added just do this:

        @generator("foo")
        class FooGen(object):
            ...
    """
    _generators = {}

    def __init__(self, gen):
        """
        Args:
            gen (str): The name of the generator to add.

        Raises:
            ValueError: If there is a similarly named generator already added.

        """
        self._gen = gen

        if gen in generator._generators:
            raise ValueError('Duplicate generator name: ' + gen)

        generator._generators[gen] = None

    def __call__(self, cls):

        generator._generators[self._gen] = cls()
        return cls

    @staticmethod
    def get():
        """Gets the list of generators.

       Returns:
           The list of registered generators.
        """
        return generator._generators


class Utils(object):
    """Various assorted static utilities."""

    @staticmethod
    def in_any_range(value, ranges):
        """Tests if a value is in a list of given closed range tuples.

        A range tuple is a closed range. That means it's inclusive of its
        start and ending values.

        Args:
            value (int): The value to test.
            range [(int, int)]: The closed range list to test value within.

        Returns:
            True if value is within the closed range, false otherwise.
        """

        return any(lower <= value <= upper for (lower, upper) in ranges)


class AID(object):
    """This class represents an Android ID or an AID.

    Attributes:
        identifier (str): The identifier name for a #define.
        value (str) The User Id (uid) of the associate define.
        found (str) The file it was found in, can be None.
        normalized_value (str): Same as value, but base 10.
    """

    def __init__(self, identifier, value, found):
        """
        Args:
            identifier: The identifier name for a #define <identifier>.
            value: The value of the AID, aka the uid.
            found (str): The file found in, not required to be specified.

        Raises:
            ValueError: if value is not a valid string number as processed by
                int(x, 0)
        """
        self.identifier = identifier
        self.value = value
        self.found = found
        self.normalized_value = str(int(value, 0))


class FSConfig(object):
    """Represents a filesystem config array entry.

    Represents a file system configuration entry for specifying
    file system capabilities.

    Attributes:
        mode (str): The mode of the file or directory.
        user (str): The uid or #define identifier (AID_SYSTEM)
        group (str): The gid or #define identifier (AID_SYSTEM)
        caps (str): The capability set.
        filename (str): The file it was found in.
    """

    def __init__(self, mode, user, group, caps, path, filename):
        """
        Args:
            mode (str): The mode of the file or directory.
            user (str): The uid or #define identifier (AID_SYSTEM)
            group (str): The gid or #define identifier (AID_SYSTEM)
            caps (str): The capability set as a list.
            filename (str): The file it was found in.
        """
        self.mode = mode
        self.user = user
        self.group = group
        self.caps = caps
        self.path = path
        self.filename = filename


class AIDHeaderParser(object):
    """Parses an android_filesystem_config.h file.

    Parses a C header file and extracts lines starting with #define AID_<name>
    It provides some basic sanity checks. The information extracted from this
    file can later be used to sanity check other things (like oem ranges) as
    well as generating a mapping of names to uids. It was primarily designed to
    parse the private/android_filesystem_config.h, but any C header should
    work.
    """

    _SKIPWORDS = ['UNUSED']
    _AID_KW = 'AID_'
    _AID_DEFINE = re.compile(r'\s*#define\s+%s.*' % _AID_KW)
    _OEM_START_KW = 'START'
    _OEM_END_KW = 'END'
    _OEM_RANGE = re.compile('AID_OEM_RESERVED_[0-9]*_{0,1}(%s|%s)' %
                            (_OEM_START_KW, _OEM_END_KW))

    # Some of the AIDS like AID_MEDIA_EX had names like mediaex
    # list a map of things to fixup until we can correct these
    # at a later date.
    _FIXUPS = {
        'media_drm': 'mediadrm',
        'media_ex': 'mediaex',
        'media_codec': 'mediacodec'
    }

    def __init__(self, aid_header):
        """
        Args:
            aid_header (str): file name for the header
                file containing AID entries.
        """
        self._aid_header = aid_header
        self._aid_name_to_value = {}
        self._aid_value_to_name = {}
        self._oem_ranges = {}

        with open(aid_header) as open_file:
            self._parse(open_file)

        try:
            self._process_and_check()
        except ValueError as exception:
            sys.exit('Error processing parsed data: "%s"' % (str(exception)))

    def _parse(self, aid_file):
        """Parses an AID header file. Internal use only.

        Args:
            aid_file (file): The open AID header file to parse.
        """

        for lineno, line in enumerate(aid_file):
            def error_message(msg):
                """Creates an error message with the current parsing state."""
                return 'Error "{}" in file: "{}" on line: {}'.format(
                    msg, self._aid_header, str(lineno))

            if AIDHeaderParser._AID_DEFINE.match(line):
                chunks = line.split()

                if any(x in chunks[1] for x in AIDHeaderParser._SKIPWORDS):
                    continue

                identifier = chunks[1]
                value = chunks[2]

                try:
                    if AIDHeaderParser._is_oem_range(identifier):
                        self._handle_oem_range(identifier, value)
                    else:
                        self._handle_aid(identifier, value)
                except ValueError as exception:
                    sys.exit(error_message(
                        '{} for "{}"'.format(exception, identifier)))

    def _handle_aid(self, identifier, value):
        """Handle an AID C #define.

        Handles an AID, sanity checking, generating the friendly name and
        adding it to the internal maps. Internal use only.

        Args:
            identifier (str): The name of the #define identifier. ie AID_FOO.
            value (str): The value associated with the identifier.

        Raises:
            ValueError: With message set to indicate the error.
        """

        # friendly name
        name = AIDHeaderParser._convert_friendly(identifier)

        # duplicate name
        if name in self._aid_name_to_value:
            raise ValueError('Duplicate aid "%s"' % identifier)

        if value in self._aid_value_to_name:
            raise ValueError('Duplicate aid value "%u" for %s' % value,
                             identifier)

        self._aid_name_to_value[name] = AID(identifier, value, self._aid_header)
        self._aid_value_to_name[value] = name

    def _handle_oem_range(self, identifier, value):
        """Handle an OEM range C #define.

        When encountering special AID defines, notably for the OEM ranges
        this method handles sanity checking and adding them to the internal
        maps. For internal use only.

        Args:
            identifier (str): The name of the #define identifier.
                ie AID_OEM_RESERVED_START/END.
            value (str): The value associated with the identifier.

        Raises:
            ValueError: With message set to indicate the error.
        """

        try:
            int_value = int(value, 0)
        except ValueError:
            raise ValueError(
                'Could not convert "%s" to integer value, got: "%s"' %
                (identifier, value))

        # convert AID_OEM_RESERVED_START or AID_OEM_RESERVED_<num>_START
        # to AID_OEM_RESERVED or AID_OEM_RESERVED_<num>
        is_start = identifier.endswith(AIDHeaderParser._OEM_START_KW)

        if is_start:
            tostrip = len(AIDHeaderParser._OEM_START_KW)
        else:
            tostrip = len(AIDHeaderParser._OEM_END_KW)

        # ending _
        tostrip = tostrip + 1

        strip = identifier[:-tostrip]
        if strip not in self._oem_ranges:
            self._oem_ranges[strip] = []

        if len(self._oem_ranges[strip]) > 2:
            raise ValueError('Too many same OEM Ranges "%s"' % identifier)

        if len(self._oem_ranges[strip]) == 1:
            tmp = self._oem_ranges[strip][0]

            if tmp == int_value:
                raise ValueError('START and END values equal %u' % int_value)
            elif is_start and tmp < int_value:
                raise ValueError('END value %u less than START value %u' %
                                 (tmp, int_value))
            elif not is_start and tmp > int_value:
                raise ValueError('END value %u less than START value %u' %
                                 (int_value, tmp))

        # Add START values to the head of the list and END values at the end.
        # Thus, the list is ordered with index 0 as START and index 1 as END.
        if is_start:
            self._oem_ranges[strip].insert(0, int_value)
        else:
            self._oem_ranges[strip].append(int_value)

    def _process_and_check(self):
        """Process, check and populate internal data structures.

        After parsing and generating the internal data structures, this method
        is responsible for sanity checking ALL of the acquired data.

        Raises:
            ValueError: With the message set to indicate the specific error.
        """

        # tuplefy the lists since range() does not like them mutable.
        self._oem_ranges = [
            AIDHeaderParser._convert_lst_to_tup(k, v)
            for k, v in self._oem_ranges.iteritems()
        ]

        # Check for overlapping ranges
        for i, range1 in enumerate(self._oem_ranges):
            for range2 in self._oem_ranges[i + 1:]:
                if AIDHeaderParser._is_overlap(range1, range2):
                    raise ValueError("Overlapping OEM Ranges found %s and %s" %
                                     (str(range1), str(range2)))

        # No core AIDs should be within any oem range.
        for aid in self._aid_value_to_name:

            if Utils.in_any_range(aid, self._oem_ranges):
                name = self._aid_value_to_name[aid]
                raise ValueError(
                    'AID "%s" value: %u within reserved OEM Range: "%s"' %
                    (name, aid, str(self._oem_ranges)))

    @property
    def oem_ranges(self):
        """Retrieves the OEM closed ranges as a list of tuples.

        Returns:
            A list of closed range tuples: [ (0, 42), (50, 105) ... ]
        """
        return self._oem_ranges

    @property
    def aids(self):
        """Retrieves the list of found AIDs.

        Returns:
            A list of AID() objects.
        """
        return self._aid_name_to_value

    @staticmethod
    def _convert_lst_to_tup(name, lst):
        """Converts a mutable list to a non-mutable tuple.

        Used ONLY for ranges and thus enforces a length of 2.

        Args:
            lst (List): list that should be "tuplefied".

        Raises:
            ValueError if lst is not a list or len is not 2.

        Returns:
            Tuple(lst)
        """
        if not lst or len(lst) != 2:
            raise ValueError('Mismatched range for "%s"' % name)

        return tuple(lst)

    @staticmethod
    def _convert_friendly(identifier):
        """
        Translate AID_FOO_BAR to foo_bar (ie name)

        Args:
            identifier (str): The name of the #define.

        Returns:
            The friendly name as a str.
        """

        name = identifier[len(AIDHeaderParser._AID_KW):].lower()

        if name in AIDHeaderParser._FIXUPS:
            return AIDHeaderParser._FIXUPS[name]

        return name

    @staticmethod
    def _is_oem_range(aid):
        """Detects if a given aid is within the reserved OEM range.

        Args:
            aid (int): The aid to test

        Returns:
            True if it is within the range, False otherwise.
        """

        return AIDHeaderParser._OEM_RANGE.match(aid)

    @staticmethod
    def _is_overlap(range_a, range_b):
        """Calculates the overlap of two range tuples.

        A range tuple is a closed range. A closed range includes its endpoints.
        Note that python tuples use () notation which collides with the
        mathematical notation for open ranges.

        Args:
            range_a: The first tuple closed range eg (0, 5).
            range_b: The second tuple closed range eg (3, 7).

        Returns:
            True if they overlap, False otherwise.
        """

        return max(range_a[0], range_b[0]) <= min(range_a[1], range_b[1])


class FSConfigFileParser(object):
    """Parses a config.fs ini format file.

    This class is responsible for parsing the config.fs ini format files.
    It collects and checks all the data in these files and makes it available
    for consumption post processed.
    """

    _AID_MATCH = re.compile('AID_[a-zA-Z]+')

    def __init__(self, config_files, oem_ranges):
        """
        Args:
            config_files ([str]): The list of config.fs files to parse.
                Note the filename is not important.
            oem_ranges ([(),()]): range tuples indicating reserved OEM ranges.
        """

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
        """Parses and verifies config.fs files. Internal use only.

        Args:
            file_name (str): The config.fs (PythonConfigParser file format)
                file to parse.

        Raises:
            Anything raised by ConfigParser.read()
        """

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

            if FSConfigFileParser._AID_MATCH.match(
                    section) and config.has_option(section, 'value'):
                FSConfigFileParser._handle_dup('AID', file_name, section,
                                               self._seen_aids[0])
                self._seen_aids[0][section] = file_name
                self._handle_aid(file_name, section, config)
            else:
                FSConfigFileParser._handle_dup('path', file_name, section,
                                               self._seen_paths)
                self._seen_paths[section] = file_name
                self._handle_path(file_name, section, config)

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
            self._files.sort(key=FSConfigFileParser._file_key)

            # sort on value of (file_name, name, value, strvalue)
            # This is only cosmetic so AIDS are arranged in ascending order
            # within the generated file.
            self._aids.sort(key=lambda item: item.normalized_value)

    def _handle_aid(self, file_name, section_name, config):
        """Verifies an AID entry and adds it to the aid list.

        Calls sys.exit() with a descriptive message of the failure.

        Args:
            file_name (str): The filename of the config file being parsed.
            section_name (str): The section name currently being parsed.
            config (ConfigParser): The ConfigParser section being parsed that
                the option values will come from.
        """

        def error_message(msg):
            """Creates an error message with current parsing state."""
            return '{} for: "{}" file: "{}"'.format(msg, section_name,
                                                    file_name)

        value = config.get(section_name, 'value')

        if not value:
            sys.exit(error_message('Found specified but unset "value"'))

        try:
            aid = AID(section_name, value, file_name)
        except ValueError:
            sys.exit(
                error_message('Invalid "value", not aid number, got: \"%s\"' %
                              value))

        # Values must be within OEM range
        if not Utils.in_any_range(int(aid.value, 0), self._oem_ranges):
            emsg = '"value" not in valid range %s, got: %s'
            emsg = emsg % (str(self._oem_ranges), value)
            sys.exit(error_message(emsg))

        # use the normalized int value in the dict and detect
        # duplicate definitions of the same value
        if aid.normalized_value in self._seen_aids[1]:
            # map of value to aid name
            aid = self._seen_aids[1][aid.normalized_value]

            # aid name to file
            file_name = self._seen_aids[0][aid]

            emsg = 'Duplicate AID value "%s" found on AID: "%s".' % (
                value, self._seen_aids[1][aid.normalized_value])
            emsg += ' Previous found in file: "%s."' % file_name
            sys.exit(error_message(emsg))

        self._seen_aids[1][aid.normalized_value] = section_name

        # Append aid tuple of (AID_*, base10(value), _path(value))
        # We keep the _path version of value so we can print that out in the
        # generated header so investigating parties can identify parts.
        # We store the base10 value for sorting, so everything is ascending
        # later.
        self._aids.append(aid)

    def _handle_path(self, file_name, section_name, config):
        """Add a file capability entry to the internal list.

        Handles a file capability entry, verifies it, and adds it to
        to the internal dirs or files list based on path. If it ends
        with a / its a dir. Internal use only.

        Calls sys.exit() on any validation error with message set.

        Args:
            file_name (str): The current name of the file being parsed.
            section_name (str): The name of the section to parse.
            config (str): The config parser.
        """

        mode = config.get(section_name, 'mode')
        user = config.get(section_name, 'user')
        group = config.get(section_name, 'group')
        caps = config.get(section_name, 'caps')

        errmsg = ('Found specified but unset option: \"%s" in file: \"' +
                  file_name + '\"')

        if not mode:
            sys.exit(errmsg % 'mode')

        if not user:
            sys.exit(errmsg % 'user')

        if not group:
            sys.exit(errmsg % 'group')

        if not caps:
            sys.exit(errmsg % 'caps')

        caps = caps.split()

        tmp = []
        for cap in caps:
            try:
                # test if string is int, if it is, use as is.
                int(cap, 0)
                tmp.append('(' + cap + ')')
            except ValueError:
                tmp.append('(1ULL << CAP_' + cap.upper() + ')')

        caps = tmp

        if len(mode) == 3:
            mode = '0' + mode

        try:
            int(mode, 8)
        except ValueError:
            sys.exit('Mode must be octal characters, got: "%s"' % mode)

        if len(mode) != 4:
            sys.exit('Mode must be 3 or 4 characters, got: "%s"' % mode)

        caps_str = '|'.join(caps)

        entry = FSConfig(mode, user, group, caps_str, section_name, file_name)
        if section_name[-1] == '/':
            self._dirs.append(entry)
        else:
            self._files.append(entry)

    @property
    def files(self):
        """Get the list of FSConfig file entries.

        Returns:
             a list of FSConfig() objects for file paths.
        """
        return self._files

    @property
    def dirs(self):
        """Get the list of FSConfig dir entries.

        Returns:
            a list of FSConfig() objects for directory paths.
        """
        return self._dirs

    @property
    def aids(self):
        """Get the list of AID entries.

        Returns:
            a list of AID() objects.
        """
        return self._aids

    @staticmethod
    def _file_key(fs_config):
        """Used as the key paramter to sort.

        This is used as a the function to the key parameter of a sort.
        it wraps the string supplied in a class that implements the
        appropriate __lt__ operator for the sort on path strings. See
        StringWrapper class for more details.

        Args:
            fs_config (FSConfig): A FSConfig entry.

        Returns:
            A StringWrapper object
        """

        # Wrapper class for custom prefix matching strings
        class StringWrapper(object):
            """Wrapper class used for sorting prefix strings.

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
            """

            def __init__(self, path):
                """
                Args:
                    path (str): the path string to wrap.
                """
                self.is_prefix = path[-1] == '*'
                if self.is_prefix:
                    self.path = path[:-1]
                else:
                    self.path = path

            def __lt__(self, other):

                # if were both suffixed the smallest string
                # is 'bigger'
                if self.is_prefix and other.is_prefix:
                    result = len(self.path) > len(other.path)
                # If I am an the suffix match, im bigger
                elif self.is_prefix:
                    result = False
                # If other is the suffix match, he's bigger
                elif other.is_prefix:
                    result = True
                # Alphabetical
                else:
                    result = self.path < other.path
                return result

        return StringWrapper(fs_config.path)

    @staticmethod
    def _handle_dup(name, file_name, section_name, seen):
        """Tracks and detects duplicates. Internal use only.

        Calls sys.exit() on a duplicate.

        Args:
            name (str): The name to use in the error reporting. The pretty
                name for the section.
            file_name (str): The file currently being parsed.
            section_name (str): The name of the section. This would be path
                or identifier depending on what's being parsed.
            seen (dict): The dictionary of seen things to check against.
        """
        if section_name in seen:
            dups = '"' + seen[section_name] + '" and '
            dups += file_name
            sys.exit('Duplicate %s "%s" found in files: %s' %
                     (name, section_name, dups))

        seen[section_name] = file_name


class BaseGenerator(object):
    """Interface for Generators.

    Base class for generators, generators should implement
    these method stubs.
    """

    def add_opts(self, opt_group):
        """Used to add per-generator options to the command line.

        Args:
            opt_group (argument group object): The argument group to append to.
                See the ArgParse docs for more details.
        """

        raise NotImplementedError("Not Implemented")

    def __call__(self, args):
        """This is called to do whatever magic the generator does.

        Args:
            args (dict): The arguments from ArgParse as a dictionary.
                ie if you specified an argument of foo in add_opts, access
                it via args['foo']
        """

        raise NotImplementedError("Not Implemented")


@generator('fsconfig')
class FSConfigGen(BaseGenerator):
    """Generates the android_filesystem_config.h file.

    Output is  used in generating fs_config_files and fs_config_dirs.
    """

    _GENERATED = textwrap.dedent("""\
        /*
         * THIS IS AN AUTOGENERATED FILE! DO NOT MODIFY
         */
        """)

    _INCLUDES = [
        '<private/android_filesystem_config.h>', '"generated_oem_aid.h"'
    ]

    _DEFINE_NO_DIRS = '#define NO_ANDROID_FILESYSTEM_CONFIG_DEVICE_DIRS'
    _DEFINE_NO_FILES = '#define NO_ANDROID_FILESYSTEM_CONFIG_DEVICE_FILES'

    _DEFAULT_WARNING = (
        '#warning No device-supplied android_filesystem_config.h,'
        ' using empty default.')

    # Long names.
    # pylint: disable=invalid-name
    _NO_ANDROID_FILESYSTEM_CONFIG_DEVICE_DIRS_ENTRY = (
        '{ 00000, AID_ROOT, AID_ROOT, 0,'
        '"system/etc/fs_config_dirs" },')

    _NO_ANDROID_FILESYSTEM_CONFIG_DEVICE_FILES_ENTRY = (
        '{ 00000, AID_ROOT, AID_ROOT, 0,'
        '"system/etc/fs_config_files" },')

    _IFDEF_ANDROID_FILESYSTEM_CONFIG_DEVICE_DIRS = (
        '#ifdef NO_ANDROID_FILESYSTEM_CONFIG_DEVICE_DIRS')
    # pylint: enable=invalid-name

    _ENDIF = '#endif'

    _OPEN_FILE_STRUCT = (
        'static const struct fs_path_config android_device_files[] = {')

    _OPEN_DIR_STRUCT = (
        'static const struct fs_path_config android_device_dirs[] = {')

    _CLOSE_FILE_STRUCT = '};'

    _GENERIC_DEFINE = "#define %s\t%s"

    _FILE_COMMENT = '// Defined in file: \"%s\"'

    def add_opts(self, opt_group):

        opt_group.add_argument(
            'fsconfig', nargs='+', help='The list of fsconfig files to parse')

        opt_group.add_argument(
            '--aid-header',
            required=True,
            help='An android_filesystem_config.h file'
            ' to parse AIDs and OEM Ranges from')

    def __call__(self, args):

        hdr = AIDHeaderParser(args['aid_header'])
        oem_ranges = hdr.oem_ranges

        parser = FSConfigFileParser(args['fsconfig'], oem_ranges)
        FSConfigGen._generate(parser.files, parser.dirs, parser.aids)

    @staticmethod
    def _to_fs_entry(fs_config):
        """
        Given an FSConfig entry, converts it to a proper
        array entry for the array entry.

        { mode, user, group, caps, "path" },

        Args:
            fs_config (FSConfig): The entry to convert to
                a valid C array entry.
        """

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
        """
        Generate the include header lines and print to stdout.
        Internal use only.
        """
        for include in FSConfigGen._INCLUDES:
            print '#include %s' % include

    @staticmethod
    def _generate(files, dirs, aids):
        """Generates an OEM android_filesystem_config.h header file to stdout.

        Args:
            files ([FSConfig]): A list of FSConfig objects for file entries.
            dirs ([FSConfig]): A list of FSConfig objects for directory
                entries.
            aids ([AIDS]): A list of AID objects for Android Id entries.
        """
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
            print FSConfigGen._DEFINE_NO_DIRS + '\n'

        if not are_files:
            print FSConfigGen._DEFINE_NO_FILES + '\n'

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


@generator('aidarray')
class AIDArrayGen(BaseGenerator):
    """Generates the android_id static array."""

    _GENERATED = ('/*\n'
                  ' * THIS IS AN AUTOGENERATED FILE! DO NOT MODIFY!\n'
                  ' */')

    _INCLUDE = '#include <private/android_filesystem_config.h>'

    _STRUCT_FS_CONFIG = textwrap.dedent("""
                         struct android_id_info {
                             const char *name;
                             unsigned aid;
                         };""")

    _OPEN_ID_ARRAY = 'static const struct android_id_info android_ids[] = {'

    _ID_ENTRY = '    { "%s", %s },'

    _CLOSE_FILE_STRUCT = '};'

    _COUNT = ('#define android_id_count \\\n'
              '    (sizeof(android_ids) / sizeof(android_ids[0]))')

    def add_opts(self, opt_group):

        opt_group.add_argument(
            'hdrfile', help='The android_filesystem_config.h'
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

        for name, aid in hdr.aids.iteritems():
            print AIDArrayGen._ID_ENTRY % (name, aid.identifier)

        print AIDArrayGen._CLOSE_FILE_STRUCT
        print
        print AIDArrayGen._COUNT
        print


@generator('oemaid')
class OEMAidGen(BaseGenerator):
    """Generates the OEM AID_<name> value header file."""

    _GENERATED = ('/*\n'
                  ' * THIS IS AN AUTOGENERATED FILE! DO NOT MODIFY!\n'
                  ' */')

    _GENERIC_DEFINE = "#define %s\t%s"

    _FILE_COMMENT = '// Defined in file: \"%s\"'

    # Intentional trailing newline for readability.
    _FILE_IFNDEF_DEFINE = ('#ifndef GENERATED_OEM_AIDS_H_\n'
                           '#define GENERATED_OEM_AIDS_H_\n')

    _FILE_ENDIF = '#endif'

    def __init__(self):

        self._old_file = None

    def add_opts(self, opt_group):

        opt_group.add_argument(
            'fsconfig', nargs='+', help='The list of fsconfig files to parse.')

        opt_group.add_argument(
            '--aid-header',
            required=True,
            help='An android_filesystem_config.h file'
            'to parse AIDs and OEM Ranges from')

    def __call__(self, args):

        hdr_parser = AIDHeaderParser(args['aid_header'])

        parser = FSConfigFileParser(args['fsconfig'], hdr_parser.oem_ranges)

        print OEMAidGen._GENERATED

        print OEMAidGen._FILE_IFNDEF_DEFINE

        for aid in parser.aids:
            self._print_aid(aid)
            print

        print OEMAidGen._FILE_ENDIF

    def _print_aid(self, aid):
        """Prints a valid #define AID identifier to stdout.

        Args:
            aid to print
        """

        # print the source file location of the AID
        found_file = aid.found
        if found_file != self._old_file:
            print OEMAidGen._FILE_COMMENT % found_file
            self._old_file = found_file

        print OEMAidGen._GENERIC_DEFINE % (aid.identifier, aid.value)


def main():
    """Main entry point for execution."""

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
