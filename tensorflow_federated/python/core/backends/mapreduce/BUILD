package(default_visibility = ["//visibility:private"])

licenses(["notice"])  # Apache 2.0

py_library(
    name = "mapreduce",
    srcs = ["__init__.py"],
    visibility = ["//tensorflow_federated/python/core/backends:__pkg__"],
    deps = [
        ":canonical_form",
        ":canonical_form_utils",
    ],
)

py_library(
    name = "canonical_form",
    srcs = ["canonical_form.py"],
    deps = [
        "//tensorflow_federated/proto/v0:tensorflow_federated_v0_py_pb2",
        "//tensorflow_federated/python/common_libs:py_typecheck",
        "//tensorflow_federated/python/core/api",
    ],
)

py_library(
    name = "canonical_form_utils",
    srcs = ["canonical_form_utils.py"],
    deps = [
        ":canonical_form",
        ":transformations",
        "//tensorflow_federated/python/common_libs:py_typecheck",
        "//tensorflow_federated/python/core/api",
        "//tensorflow_federated/python/core/framework",
        "//tensorflow_federated/python/core/utils",
    ],
)

py_test(
    name = "canonical_form_utils_test",
    size = "large",
    srcs = ["canonical_form_utils_test.py"],
    deps = [
        ":canonical_form",
        ":canonical_form_utils",
        ":test_utils",
        "//tensorflow_federated",
        "//tensorflow_federated/python/core/api:computation_types",
        "//tensorflow_federated/python/core/api:placements",
        "//tensorflow_federated/python/core/impl:computation_wrapper_instances",
        "//tensorflow_federated/python/core/impl/compiler:building_blocks",
        "//tensorflow_federated/python/core/utils:computation_utils",
    ],
)

py_library(
    name = "test_utils",
    testonly = True,
    srcs = ["test_utils.py"],
    deps = [
        ":canonical_form",
        "//tensorflow_federated",
    ],
)

py_library(
    name = "transformations",
    srcs = ["transformations.py"],
    srcs_version = "PY2AND3",
    deps = [
        "//tensorflow_federated/python/common_libs:py_typecheck",
        "//tensorflow_federated/python/core/api",
        "//tensorflow_federated/python/core/framework",
    ],
)

py_test(
    name = "transformations_test",
    size = "medium",
    srcs = ["transformations_test.py"],
    deps = [
        ":canonical_form_utils",
        ":test_utils",
        ":transformations",
        "//tensorflow_federated/proto/v0:tensorflow_federated_v0_py_pb2",
        "//tensorflow_federated/python/core/api:computation_types",
        "//tensorflow_federated/python/core/api:intrinsics",
        "//tensorflow_federated/python/core/api:placements",
        "//tensorflow_federated/python/core/impl:computation_constructing_utils",
        "//tensorflow_federated/python/core/impl:computation_wrapper_instances",
        "//tensorflow_federated/python/core/impl:intrinsic_defs",
        "//tensorflow_federated/python/core/impl:transformation_utils",
        "//tensorflow_federated/python/core/impl:transformations",
        "//tensorflow_federated/python/core/impl/compiler:building_block_analysis",
        "//tensorflow_federated/python/core/impl/compiler:building_blocks",
        "//tensorflow_federated/python/core/impl/compiler:tree_analysis",
    ],
)
