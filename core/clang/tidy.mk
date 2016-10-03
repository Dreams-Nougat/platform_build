#
# Copyright (C) 2016 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# Most Android source files are not clang-tidy clean yet.
# Global tidy checks include only google*, performance*,
# and misc-macro-parentheses, but not google-readability*
# or google-runtime-references.
ifndef DEFAULT_GLOBAL_TIDY_CHECKS
DEFAULT_GLOBAL_TIDY_CHECKS := \
  $(subst $(space),, \
    -*,google* \
    ,misc-macro-parentheses \
    ,performance* \
    ,-google-readability* \
    ,-google-runtime-references \
  )
endif

# There are too many clang-tidy warnings in external and vendor projects.
# Enable only some google checks for these projects.
ifndef DEFAULT_EXTERNAL_VENDOR_TIDY_CHECKS
DEFAULT_EXTERNAL_VENDOR_TIDY_CHECKS := \
  $(subst $(space),, \
    -*,google* \
    ,-google-build-using-namespace \
    ,-google-default-arguments \
    ,-google-explicit-constructor \
    ,-google-readability* \
    ,-google-runtime-int \
    ,-google-runtime-references \
  )
endif

# Every word in DEFAULT_LOCAL_TIDY_CHECKS list has the following format:
#   <local_path_prefix>:,<tidy-checks>
# The last matched local_path_prefix should be the most specific to be used.
DEFAULT_LOCAL_TIDY_CHECKS := \
  external/:$(DEFAULT_EXTERNAL_VENDOR_TIDY_CHECKS) \
  external/google:$(DEFAULT_GLOBAL_TIDY_CHECKS) \
  external/webrtc:$(DEFAULT_GLOBAL_TIDY_CHECKS) \
  frameworks/compile/mclinker/:$(DEFAULT_EXTERNAL_VENDOR_TIDY_CHECKS) \
  hardware/qcom:$(DEFAULT_EXTERNAL_VENDOR_TIDY_CHECKS) \
  vendor/:$(DEFAULT_EXTERNAL_VENDOR_TIDY_CHECKS) \
  vendor/google:$(DEFAULT_GLOBAL_TIDY_CHECKS) \

# Returns 2nd word of $(1) if $(2) has prefix of the 1st word of $(1).
define find_default_local_tidy_check2
$(if $(filter $(word 1,$(1))%,$(2)/),$(word 2,$(1)))
endef

# Returns 2nd part of $(1) if $(2) has prefix of the 1st part of $(1).
define find_default_local_tidy_check
$(call find_default_local_tidy_check2,$(subst :,$(space),$(1)),$(2))
endef

# Returns the default tidy check list for local project path $(1).
# Match $(1) with all patterns in DEFAULT_LOCAL_TIDY_CHECKS and use the last
# most specific pattern.
define default_global_tidy_checks
$(lastword \
  $(DEFAULT_GLOBAL_TIDY_CHECKS) \
  $(foreach pattern,$(DEFAULT_LOCAL_TIDY_CHECKS), \
    $(call find_default_local_tidy_check,$(pattern),$(1)) \
  ) \
)
endef

# Give warnings to header files only in selected directories.
# Do not give warnings to external or vendor header files,
# which contain too many warnings.
DEFAULT_TIDY_HEADER_DIRS := \
  $(subst $(space),, \
     art/ \
    |bionic/ \
    |bootable/ \
    |build/ \
    |cts/ \
    |dalvik/ \
    |developers/ \
    |development/ \
    |frameworks/ \
    |libcore/ \
    |libnativehelper/ \
    |system/ \
  )

# Default filter contains current directory $1 and DEFAULT_TIDY_HEADER_DIRS.
define default_tidy_header_filter
  -header-filter="($(subst $(space),,$1|$(DEFAULT_TIDY_HEADER_DIRS)))"
endef
