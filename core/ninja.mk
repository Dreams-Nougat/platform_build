KATI ?= $(HOST_OUT_EXECUTABLES)/ckati

KATI_OUTPUT_PATTERNS := $(PRODUCT_OUT)/build%.ninja $(PRODUCT_OUT)/ninja%.sh
NINJA_GOALS := fastincremental generateonly droid showcommands
# A list of goals which affect pasing of make.
SPECIAL_MAKE_GOALS := \
	$(SPECIAL_MAKE_GOALS) \
	$(dont_bother_goals) \
	%tests \
	APP-% \
	DUMP_% \
	ECLIPSE-% \
	PRODUCT-% \
	boottarball-nodeps \
	btnod \
	build-art% \
	build_kernel-nodeps \
	checkbuild \
	clean-oat% \
	continuous_instrumentation_tests \
	continuous_native_tests \
	cts \
	custom_images \
	deps-license \
	dicttool_aosp \
	dist \
	dump-products \
	dumpvar-% \
	eng \
	fusion \
	oem_image \
	online-system-api-sdk-docs \
	pdk \
	platform \
	platform-java \
	product-graph \
	samplecode \
	sdk \
	sdk_addon \
	sdk_repo \
	snod \
	stnod \
	systemimage-nodeps \
	systemtarball-nodeps \
	target-files-package \
	test-art% \
	user \
	userdataimage \
	userdebug \
	valgrind-test-art% \
	win_sdk \
	winsdk-tools

ANDROID_TARGETS := $(filter-out $(KATI_OUTPUT_PATTERNS) $(NINJA_GOALS),$(ORIGINAL_MAKECMDGOALS))
KATI_TARGETS := $(if $(filter $(SPECIAL_MAKE_GOALS),$(ANDROID_TARGETS)),$(ANDROID_TARGETS),)

define replace_space_and_slash
$(subst /,_,$(subst $(space),_,$(sort $1)))
endef

KATI_NINJA_SUFFIX :=
ifneq ($(KATI_TARGETS),)
KATI_NINJA_SUFFIX := $(KATI_NINJA_SUFFIX)-$(call replace_space_and_slash,$(KATI_TARGETS))
endif
ifneq ($(ONE_SHOT_MAKEFILE),)
KATI_NINJA_SUFFIX := $(KATI_NINJA_SUFFIX)-mmm-$(call replace_space_and_slash,$(ONE_SHOT_MAKEFILE))
endif
ifneq ($(BUILD_MODULES_IN_PATHS),)
KATI_NINJA_SUFFIX := $(KATI_NINJA_SUFFIX)-mmma-$(call replace_space_and_slash,$(BUILD_MODULES_IN_PATHS))
endif

KATI_BUILD_NINJA := $(PRODUCT_OUT)/build$(KATI_NINJA_SUFFIX).ninja
KATI_NINJA_SH := $(PRODUCT_OUT)/ninja$(KATI_NINJA_SUFFIX).sh
KATI_OUTPUTS := $(KATI_BUILD_NINJA) $(KATI_NINJA_SH)

ifeq (,$(NINJA_STATUS))
NINJA_STATUS := [%p %s/%t]$(space)
endif

ifneq (,$(filter showcommands,$(ORIGINAL_MAKECMDGOALS)))
NINJA_ARGS += "-v"
PHONY: showcommands
showcommands: droid
endif

ifeq (,$(filter generateonly,$(ORIGINAL_MAKECMDGOALS)))
fastincremental droid $(ANDROID_TARGETS): ninja.intermediate
	@#empty

.INTERMEDIATE: ninja.intermediate
ninja.intermediate: $(KATI_OUTPUTS)
	@echo Starting build with ninja
	$(hide) PATH=prebuilts/ninja/$(HOST_PREBUILT_TAG)/:$$PATH NINJA_STATUS="$(NINJA_STATUS)" $(KATI_NINJA_SH) -C $(TOP) $(NINJA_ARGS) $(ANDROID_TARGETS)
else
generateonly droid $(ANDROID_TARGETS): $(KATI_OUTPUTS)
	@#empty
endif

ifeq (,$(filter fastincremental,$(ORIGINAL_MAKECMDGOALS)))
KATI_FORCE := FORCE
endif

$(KATI_OUTPUTS): kati.intermediate $(KATI_FORCE)

.INTERMEDIATE: kati.intermediate
kati.intermediate: $(KATI)
	@echo Running kati to generate build$(KATI_NINJA_SUFFIX).ninja...
	@#TODO: use separate ninja file for mm or single target build
	$(hide) $(KATI) --ninja --ninja_dir=$(PRODUCT_OUT) --ninja_suffix=$(KATI_NINJA_SUFFIX) --regen --ignore_dirty=$(OUT_DIR)/% --ignore_optional_include=$(OUT_DIR)/%.P --detect_android_echo --use_find_emulator $(KATI_REMOTE_NUM_JOBS_FLAG) -f build/core/main.mk $(or $(KATI_TARGETS),--gen_all_phony_targets) USE_NINJA=false

KATI_CXX := $(CLANG_CXX) $(CLANG_HOST_GLOBAL_CPPFLAGS)
KATI_LD := $(CLANG_CXX) $(CLANG_HOST_GLOBAL_LDFLAGS)
# Build static ckati. Unfortunately Mac OS X doesn't officially support static exectuables.
ifeq ($(BUILD_OS),linux)
KATI_LD += -static
endif

KATI_INTERMEDIATES_PATH := $(HOST_OUT_INTERMEDIATES)/EXECUTABLES/ckati_intermediates
KATI_BIN_PATH := $(HOST_OUT_EXECUTABLES)
include build/kati/Makefile.ckati

.PHONY: FORCE
FORCE:
