# Copyright (C) 2012 The Android Open Source Project
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

# Clean steps that need global knowledge of individual modules.
# This file must be included after all Android.mks have been loaded.

#######################################################
# Checks the current build configurations against the previous build,
# clean artifacts in TARGET_COMMON_OUT_ROOT if necessary.
# If a package's resource overlay has been changed, its R class needs to be
# regenerated.
previous_package_overlay_config := $(TARGET_OUT_COMMON_INTERMEDIATES)/APPS/previous_overlays.txt
current_package_overlay_config := $(TARGET_OUT_COMMON_INTERMEDIATES)/APPS/current_overlays.txt
current_all_packages_config := $(dir $(current_package_overlay_config))current_packages.txt

$(shell rm -rf $(current_package_overlay_config) \
    && mkdir -p $(dir $(current_package_overlay_config)) \
    && touch $(current_package_overlay_config))
$(shell echo '$(PACKAGES)' > $(current_all_packages_config))
$(foreach p, $(PACKAGES), $(if $(PACKAGES.$(p).RESOURCE_OVERLAYS), \
  $(shell echo '$(p)' '$(PACKAGES.$(p).RESOURCE_OVERLAYS)' >> $(current_package_overlay_config))))

ifneq (,$(wildcard $(previous_package_overlay_config)))
packages_overlay_changed := $(shell build/tools/diff_package_overlays.py \
    $(current_all_packages_config) $(current_package_overlay_config) \
    $(previous_package_overlay_config))
ifneq (,$(packages_overlay_changed))
overlay_cleanup_cmd := $(strip rm -rf $(foreach p, $(packages_overlay_changed),\
    $(TARGET_OUT_COMMON_INTERMEDIATES)/APPS/$(p)_intermediates))
$(info *** Overlay change detected, clean shared intermediate files...)
$(info *** $(overlay_cleanup_cmd))
$(shell $(overlay_cleanup_cmd))
overlay_cleanup_cmd :=
endif
packages_overlay_changed :=
endif

# Now current becomes previous.
$(shell mv -f $(current_package_overlay_config) $(previous_package_overlay_config))

previous_package_overlay_config :=
current_package_overlay_config :=
current_all_packages_config :=

#######################################################
# Check if we need to delete obsolete generated java files.
# When an aidl/proto/etc file gets deleted (or renamed), the generated java file is obsolete.
previous_gen_java_config := $(TARGET_OUT_COMMON_INTERMEDIATES)/previous_gen_java_config.mk
current_gen_java_config := $(TARGET_OUT_COMMON_INTERMEDIATES)/current_gen_java_config.mk

$(shell rm -rf $(current_gen_java_config) \
  && mkdir -p $(dir $(current_gen_java_config))\
  && touch $(current_gen_java_config))
-include $(previous_gen_java_config)

intermediates_to_clean :=
modules_with_gen_java_files :=
$(foreach p, $(ALL_MODULES), \
  $(eval gs := $(strip $(ALL_MODULES.$(p).AIDL_FILES)\
                       $(ALL_MODULES.$(p).PROTO_FILES)\
                       $(ALL_MODULES.$(p).RS_FILES)))\
  $(if $(gs),\
    $(eval modules_with_gen_java_files += $(p))\
    $(shell echo 'GEN_SRC_FILES.$(p) := $(gs)' >> $(current_gen_java_config)))\
  $(if $(filter-out $(gs),$(GEN_SRC_FILES.$(p))),\
    $(eval intermediates_to_clean += $(ALL_MODULES.$(p).INTERMEDIATE_SOURCE_DIR))))
intermediates_to_clean := $(strip $(intermediates_to_clean))
ifdef intermediates_to_clean
$(info *** Obsolete generated java files detected, clean intermediate files...)
$(info *** rm -rf $(intermediates_to_clean))
$(shell rm -rf $(intermediates_to_clean))
intermediates_to_clean :=
endif

# For modules not loaded by the current build (e.g. you are running mm/mmm),
# we copy the info from the previous bulid.
$(foreach p, $(filter-out $(ALL_MODULES),$(MODULES_WITH_GEN_JAVA_FILES)),\
  $(shell echo 'GEN_SRC_FILES.$(p) := $(GEN_SRC_FILES.$(p))' >> $(current_gen_java_config)))
MODULES_WITH_GEN_JAVA_FILES := $(sort $(MODULES_WITH_GEN_JAVA_FILES) $(modules_with_gen_java_files))
$(shell echo 'MODULES_WITH_GEN_JAVA_FILES := $(MODULES_WITH_GEN_JAVA_FILES)' >> $(current_gen_java_config))

# Now current becomes previous.
$(shell cmp $(current_gen_java_config) $(previous_gen_java_config) > /dev/null 2>&1 || mv -f $(current_gen_java_config) $(previous_gen_java_config))

MODULES_WITH_GEN_JAVA_FILES :=
modules_with_gen_java_files :=
previous_gen_java_config :=
current_gen_java_config :=

#######################################################
# Check if we need to delete obsolete installed files.
# This won't work with mm/mmm, so disable it there.
ifndef ONE_SHOT_MAKEFILE
# Nor will it work with SANITIZE_TARGET, since that expects
# to keep the old installed files in order to produce a full
# build
ifndef SANITIZE_TARGET
previous_installed_config := $(PRODUCT_OUT)/previous_installed_files.mk
current_installed_config := $(PRODUCT_OUT)/current_installed_files.mk

$(shell rm -rf $(current_installed_config) \
  && mkdir -p $(dir $(current_installed_config))\
  && touch $(current_installed_config))
previous_installed_files :=
-include $(previous_installed_config)

installed_files_to_clean := $(filter-out $(ALL_INSTALLED_FILES),$(previous_installed_files))
ifdef installed_files_to_clean
# Exclude files that don't exist
installed_files_to_clean := $(strip $(foreach f,$(installed_files_to_clean),$(wildcard $(f))))
ifdef installed_files_to_clean
$(info *** Obsolete installed files detected, cleaning...)
$(info *** rm -rf $(installed_files_to_clean))
$(shell rm -rf $(installed_files_to_clean))
endif
endif
define dump_to_installed_files
$(if $(1),$(shell echo "previous_installed_files += $(1)" >> $(current_installed_config)))
endef
$(call dump_to_installed_files,$(wordlist 1,500,$(ALL_INSTALLED_FILES)))
$(call dump_to_installed_files,$(wordlist 501,1000,$(ALL_INSTALLED_FILES)))
$(call dump_to_installed_files,$(wordlist 1001,1500,$(ALL_INSTALLED_FILES)))
$(call dump_to_installed_files,$(wordlist 1501,2000,$(ALL_INSTALLED_FILES)))
$(call dump_to_installed_files,$(wordlist 2001,2500,$(ALL_INSTALLED_FILES)))
$(call dump_to_installed_files,$(wordlist 2501,3000,$(ALL_INSTALLED_FILES)))
$(call dump_to_installed_files,$(wordlist 3001,3500,$(ALL_INSTALLED_FILES)))
$(call dump_to_installed_files,$(wordlist 3501,4000,$(ALL_INSTALLED_FILES)))
$(call dump_to_installed_files,$(wordlist 4001,4500,$(ALL_INSTALLED_FILES)))
$(call dump_to_installed_files,$(wordlist 4501,5000,$(ALL_INSTALLED_FILES)))
$(call dump_to_installed_files,$(wordlist 5001,5500,$(ALL_INSTALLED_FILES)))
$(call dump_to_installed_files,$(wordlist 5501,6000,$(ALL_INSTALLED_FILES)))
$(call dump_to_installed_files,$(wordlist 6001,6500,$(ALL_INSTALLED_FILES)))
$(call dump_to_installed_files,$(wordlist 6501,7000,$(ALL_INSTALLED_FILES)))
$(call dump_to_installed_files,$(wordlist 7001,7500,$(ALL_INSTALLED_FILES)))
$(call dump_to_installed_files,$(wordlist 7501,8000,$(ALL_INSTALLED_FILES)))
$(call dump_to_installed_files,$(wordlist 8001,8500,$(ALL_INSTALLED_FILES)))
$(call dump_to_installed_files,$(wordlist 8501,9000,$(ALL_INSTALLED_FILES)))
$(call dump_to_installed_files,$(wordlist 9001,9500,$(ALL_INSTALLED_FILES)))
$(call dump_to_installed_files,$(wordlist 9501,10000,$(ALL_INSTALLED_FILES)))
$(call dump_to_installed_files,$(wordlist 10001,10500,$(ALL_INSTALLED_FILES)))
$(call dump_to_installed_files,$(wordlist 10501,11000,$(ALL_INSTALLED_FILES)))

# Replace previous with current if necessary
$(shell cmp $(current_installed_config) $(previous_installed_config) >/dev/null 2>&1 || mv -f $(current_installed_config) $(previous_installed_config))

previous_installed_config :=
current_installed_config :=
previous_installed_files :=
installed_files_to_clean :=
endif
endif
