# Lint as: python2, python3
# Copyright 2019, The TensorFlow Federated Authors.
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
"""Tests for transformations.py."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from absl.testing import absltest

import tensorflow as tf

import tensorflow_federated as tff

from tensorflow_federated.proto.v0 import computation_pb2
from tensorflow_federated.python.core.backends.mapreduce import canonical_form_utils
from tensorflow_federated.python.core.backends.mapreduce import test_utils
from tensorflow_federated.python.core.backends.mapreduce import transformations
from tensorflow_federated.python.core.impl import tree_analysis


class TransformationsTest(absltest.TestCase):

  def test_example_training_comp_reduces(self):
    training_comp = test_utils.construct_example_training_comp()
    self.assertIsInstance(
        test_utils.computation_to_building_block(training_comp.next),
        tff.framework.Lambda)


class CheckExtractionResultTest(absltest.TestCase):

  def test_raises_on_none_args(self):
    with self.assertRaisesRegex(TypeError, 'None'):
      transformations.check_extraction_result(
          None, tff.framework.Reference('x', tf.int32))
    with self.assertRaisesRegex(TypeError, 'None'):
      transformations.check_extraction_result(
          tff.framework.Reference('x', tf.int32), None)

  def test_raises_function_and_call(self):
    function = tff.framework.Reference('f',
                                       tff.FunctionType(tf.int32, tf.int32))
    integer_ref = tff.framework.Reference('x', tf.int32)
    call = tff.framework.Call(function, integer_ref)
    with self.assertRaisesRegex(transformations.CanonicalFormCompilationError,
                                'we have the functional type'):
      transformations.check_extraction_result(function, call)

  def test_raises_non_function_and_compiled_computation(self):
    init = canonical_form_utils.get_iterative_process_for_canonical_form(
        test_utils.get_temperature_sensor_example()).initialize
    compiled_computation = (
        test_utils.computation_to_building_block(init).argument.function)
    integer_ref = tff.framework.Reference('x', tf.int32)
    with self.assertRaisesRegex(transformations.CanonicalFormCompilationError,
                                'we have the non-functional type'):
      transformations.check_extraction_result(integer_ref, compiled_computation)

  def test_raises_function_and_compiled_computation_of_different_type(self):
    init = canonical_form_utils.get_iterative_process_for_canonical_form(
        test_utils.get_temperature_sensor_example()).initialize
    compiled_computation = (
        test_utils.computation_to_building_block(init).argument.function)
    function = tff.framework.Reference('f',
                                       tff.FunctionType(tf.int32, tf.int32))
    with self.assertRaisesRegex(transformations.CanonicalFormCompilationError,
                                'incorrect TFF type'):
      transformations.check_extraction_result(function, compiled_computation)

  def test_raises_tensor_and_call_to_not_compiled_computation(self):
    function = tff.framework.Reference('f',
                                       tff.FunctionType(tf.int32, tf.int32))
    ref_to_int = tff.framework.Reference('x', tf.int32)
    called_fn = tff.framework.Call(function, ref_to_int)
    with self.assertRaisesRegex(transformations.CanonicalFormCompilationError,
                                'missing'):
      transformations.check_extraction_result(ref_to_int, called_fn)

  def test_passes_function_and_compiled_computation_of_same_type(self):
    init = canonical_form_utils.get_iterative_process_for_canonical_form(
        test_utils.get_temperature_sensor_example()).initialize
    compiled_computation = (
        test_utils.computation_to_building_block(init).argument.function)
    function = tff.framework.Reference('f', compiled_computation.type_signature)
    transformations.check_extraction_result(function, compiled_computation)


class ConsolidateAndExtractTest(absltest.TestCase):

  def test_raises_on_none(self):
    with self.assertRaises(TypeError):
      transformations.consolidate_and_extract_local_processing(None)

  def test_raises_reference_to_functional_type(self):
    function_type = tff.FunctionType(tf.int32, tf.int32)
    ref = tff.framework.Reference('x', function_type)
    with self.assertRaisesRegex(ValueError, 'of functional type passed'):
      transformations.consolidate_and_extract_local_processing(ref)

  def test_already_reduced_case(self):
    init = canonical_form_utils.get_iterative_process_for_canonical_form(
        test_utils.get_temperature_sensor_example()).initialize

    comp = test_utils.computation_to_building_block(init)

    result = transformations.consolidate_and_extract_local_processing(comp)

    self.assertIsInstance(result, tff.framework.CompiledComputation)
    self.assertIsInstance(result.proto, computation_pb2.Computation)
    self.assertEqual(result.proto.WhichOneof('computation'), 'tensorflow')

  def test_reduces_unplaced_lambda_leaving_type_signature_alone(self):
    lam = tff.framework.Lambda('x', tf.int32,
                               tff.framework.Reference('x', tf.int32))
    extracted_tf = transformations.consolidate_and_extract_local_processing(lam)
    self.assertIsInstance(extracted_tf, tff.framework.CompiledComputation)
    self.assertEqual(extracted_tf.type_signature, lam.type_signature)

  def test_reduces_unplaced_lambda_to_equivalent_tf(self):
    lam = tff.framework.Lambda('x', tf.int32,
                               tff.framework.Reference('x', tf.int32))
    extracted_tf = transformations.consolidate_and_extract_local_processing(lam)
    executable_tf = tff.framework.building_block_to_computation(extracted_tf)
    executable_lam = tff.framework.building_block_to_computation(lam)
    for k in range(10):
      self.assertEqual(executable_tf(k), executable_lam(k))

  def test_reduces_federated_identity_to_member_identity(self):
    fed_int_type = tff.FederatedType(tf.int32, tff.CLIENTS)
    lam = tff.framework.Lambda('x', fed_int_type,
                               tff.framework.Reference('x', fed_int_type))
    extracted_tf = transformations.consolidate_and_extract_local_processing(lam)
    self.assertIsInstance(extracted_tf, tff.framework.CompiledComputation)
    unplaced_function_type = tff.FunctionType(fed_int_type.member,
                                              fed_int_type.member)
    self.assertEqual(extracted_tf.type_signature, unplaced_function_type)

  def test_reduces_federated_map_to_equivalent_function(self):
    lam = tff.framework.Lambda('x', tf.int32,
                               tff.framework.Reference('x', tf.int32))
    arg = tff.framework.Reference('arg',
                                  tff.FederatedType(tf.int32, tff.CLIENTS))
    mapped_fn = tff.framework.create_federated_map_or_apply(lam, arg)
    extracted_tf = transformations.consolidate_and_extract_local_processing(
        mapped_fn)
    self.assertIsInstance(extracted_tf, tff.framework.CompiledComputation)
    executable_tf = tff.framework.building_block_to_computation(extracted_tf)
    executable_lam = tff.framework.building_block_to_computation(lam)
    for k in range(10):
      self.assertEqual(executable_tf(k), executable_lam(k))

  def test_reduces_federated_apply_to_equivalent_function(self):
    lam = tff.framework.Lambda('x', tf.int32,
                               tff.framework.Reference('x', tf.int32))
    arg = tff.framework.Reference('arg',
                                  tff.FederatedType(tf.int32, tff.CLIENTS))
    mapped_fn = tff.framework.create_federated_map_or_apply(lam, arg)
    extracted_tf = transformations.consolidate_and_extract_local_processing(
        mapped_fn)
    self.assertIsInstance(extracted_tf, tff.framework.CompiledComputation)
    executable_tf = tff.framework.building_block_to_computation(extracted_tf)
    executable_lam = tff.framework.building_block_to_computation(lam)
    for k in range(10):
      self.assertEqual(executable_tf(k), executable_lam(k))

  def test_reduces_federated_value_at_server_to_equivalent_noarg_function(self):
    federated_value = tff.federated_value(0, tff.SERVER)._comp
    extracted_tf = transformations.consolidate_and_extract_local_processing(
        federated_value)
    executable_tf = tff.framework.building_block_to_computation(extracted_tf)
    self.assertEqual(executable_tf(), 0)

  def test_reduces_federated_value_at_clients_to_equivalent_noarg_function(
      self):
    federated_value = tff.federated_value(0, tff.CLIENTS)._comp
    extracted_tf = transformations.consolidate_and_extract_local_processing(
        federated_value)
    executable_tf = tff.framework.building_block_to_computation(extracted_tf)
    self.assertEqual(executable_tf(), 0)

  def test_reduces_lambda_returning_empty_tuple_to_tf(self):
    self.skipTest('Depends on a lower level fix, currently in review.')
    empty_tuple = tff.framework.Tuple([])
    lam = tff.framework.Lambda('x', tf.int32, empty_tuple)
    extracted_tf = transformations.consolidate_and_extract_local_processing(lam)
    self.assertIsInstance(extracted_tf, tff.framework.CompiledComputation)


class ForceAlignAndSplitByIntrinsicTest(absltest.TestCase):

  def test_returns_comps_with_federated_broadcast(self):
    iterative_process = test_utils.construct_example_training_comp()
    comp = test_utils.computation_to_building_block(iterative_process.next)
    uri = tff.framework.FEDERATED_BROADCAST.uri
    before, after = transformations.force_align_and_split_by_intrinsic(
        comp, uri)

    def _predicate(comp):
      return tff.framework.is_called_intrinsic(comp, uri)

    self.assertIsInstance(comp, tff.framework.Lambda)
    self.assertEqual(tree_analysis.count(comp, _predicate), 3)
    self.assertIsInstance(before, tff.framework.Lambda)
    self.assertEqual(tree_analysis.count(before, _predicate), 0)
    self.assertEqual(before.parameter_type, comp.parameter_type)
    self.assertIsInstance(after, tff.framework.Lambda)
    self.assertEqual(tree_analysis.count(after, _predicate), 0)
    self.assertEqual(after.result.type_signature, comp.result.type_signature)

  def test_returns_comps_with_federated_aggregate(self):
    iterative_process = test_utils.construct_example_training_comp()
    comp = test_utils.computation_to_building_block(iterative_process.next)
    uri = tff.framework.FEDERATED_AGGREGATE.uri
    before, after = transformations.force_align_and_split_by_intrinsic(
        comp, uri)

    def _predicate(comp):
      return tff.framework.is_called_intrinsic(comp, uri)

    self.assertIsInstance(comp, tff.framework.Lambda)
    self.assertEqual(tree_analysis.count(comp, _predicate), 2)
    self.assertIsInstance(before, tff.framework.Lambda)
    self.assertEqual(tree_analysis.count(before, _predicate), 0)
    self.assertEqual(before.parameter_type, comp.parameter_type)
    self.assertIsInstance(after, tff.framework.Lambda)
    self.assertEqual(tree_analysis.count(after, _predicate), 0)
    self.assertEqual(after.result.type_signature, comp.result.type_signature)


class ExtractArgumentsTest(absltest.TestCase):

  def test_raises_on_none(self):
    with self.assertRaises(TypeError):
      transformations.zip_selection_as_argument_to_lower_level_lambda(None, [0])

  def test_raises_on_non_lambda_comp(self):
    ref = tff.framework.Reference('x', [tf.int32])
    with self.assertRaises(TypeError):
      transformations.zip_selection_as_argument_to_lower_level_lambda(ref, [0])

  def test_raises_on_none_selections(self):
    lam = tff.framework.Lambda('x', tf.int32,
                               tff.framework.Reference('x', [tf.int32]))
    with self.assertRaises(TypeError):
      transformations.zip_selection_as_argument_to_lower_level_lambda(lam, None)

  def test_raises_on_selection_tuple(self):
    lam = tff.framework.Lambda('x', tf.int32,
                               tff.framework.Reference('x', [tf.int32]))
    with self.assertRaises(TypeError):
      transformations.zip_selection_as_argument_to_lower_level_lambda(lam, (0))

  def test_raises_on_non_tuple_parameter(self):
    lam = tff.framework.Lambda('x', tf.int32,
                               tff.framework.Reference('x', tf.int32))
    with self.assertRaises(TypeError):
      transformations.zip_selection_as_argument_to_lower_level_lambda(
          lam, [[0]])

  def test_raises_on_selection_from_non_tuple(self):
    lam = tff.framework.Lambda('x', [tf.int32],
                               tff.framework.Reference('x', [tf.int32]))
    with self.assertRaisesRegex(TypeError, 'nonexistent index'):
      transformations.zip_selection_as_argument_to_lower_level_lambda(
          lam, [[0, 0]])

  def test_raises_on_non_int_index(self):
    lam = tff.framework.Lambda('x', [tf.int32],
                               tff.framework.Reference('x', [('a', tf.int32)]))
    with self.assertRaises(TypeError):
      transformations.zip_selection_as_argument_to_lower_level_lambda(
          lam, [['a']])

  def test_raises_on_non_federated_selection(self):
    lam = tff.framework.Lambda('x', [tf.int32],
                               tff.framework.Reference('x', [tf.int32]))
    with self.assertRaises(TypeError):
      transformations.zip_selection_as_argument_to_lower_level_lambda(
          lam, [[0]])

  def test_raises_on_selections_at_different_placements(self):
    fed_at_clients = tff.FederatedType(tf.int32, tff.CLIENTS)
    fed_at_server = tff.FederatedType(tf.int32, tff.SERVER)
    tuple_of_federated_types = tff.NamedTupleType(
        [fed_at_clients, fed_at_server])
    lam = tff.framework.Lambda(
        'x', tuple_of_federated_types,
        tff.framework.Selection(
            tff.framework.Reference('x', tuple_of_federated_types), index=0))
    with self.assertRaisesRegex(ValueError, 'at the same placement.'):
      transformations.zip_selection_as_argument_to_lower_level_lambda(
          lam, [[0], [1]])

  def test_binds_single_element_tuple_to_lower_lambda(self):
    fed_at_clients = tff.FederatedType(tf.int32, tff.CLIENTS)
    fed_at_server = tff.FederatedType(tf.int32, tff.SERVER)
    tuple_of_federated_types = tff.NamedTupleType(
        [fed_at_clients, fed_at_server])
    lam = tff.framework.Lambda(
        'x', tuple_of_federated_types,
        tff.framework.Selection(
            tff.framework.Reference('x', tuple_of_federated_types), index=0))
    zeroth_index_extracted = (
        transformations.zip_selection_as_argument_to_lower_level_lambda(
            lam, [[0]]))
    self.assertEqual(zeroth_index_extracted.type_signature, lam.type_signature)
    self.assertIsInstance(zeroth_index_extracted, tff.framework.Lambda)
    self.assertIsInstance(zeroth_index_extracted.result, tff.framework.Call)
    self.assertIsInstance(zeroth_index_extracted.result.function,
                          tff.framework.Lambda)
    self.assertEqual(
        str(zeroth_index_extracted.result.function),
        '(_var2 -> federated_map(<(_var3 -> _var3[0]),_var2>))')
    self.assertEqual(
        str(zeroth_index_extracted.result.argument),
        'federated_map(<(_var4 -> <_var4>),<_var1[0]>[0]>)')

  def test_binds_single_argument_to_lower_lambda(self):
    fed_at_clients = tff.FederatedType(tf.int32, tff.CLIENTS)
    fed_at_server = tff.FederatedType(tf.int32, tff.SERVER)
    tuple_of_federated_types = tff.NamedTupleType(
        [fed_at_clients, fed_at_server])
    lam = tff.framework.Lambda(
        'x', tuple_of_federated_types,
        tff.framework.Selection(
            tff.framework.Reference('x', tuple_of_federated_types), index=0))
    zeroth_index_extracted = transformations.bind_single_selection_as_argument_to_lower_level_lambda(
        lam, 0)
    self.assertEqual(zeroth_index_extracted.type_signature, lam.type_signature)
    self.assertIsInstance(zeroth_index_extracted, tff.framework.Lambda)
    self.assertIsInstance(zeroth_index_extracted.result, tff.framework.Call)
    self.assertIsInstance(zeroth_index_extracted.result.function,
                          tff.framework.Lambda)
    self.assertRegex(
        str(zeroth_index_extracted.result.function), r'\((.{4})1 -> (\1)1\)')
    self.assertEqual(str(zeroth_index_extracted.result.argument), '_var1[0]')

  def test_binding_single_arg_leaves_no_unbound_references(self):
    fed_at_clients = tff.FederatedType(tf.int32, tff.CLIENTS)
    fed_at_server = tff.FederatedType(tf.int32, tff.SERVER)
    tuple_of_federated_types = tff.NamedTupleType(
        [fed_at_clients, fed_at_server])
    lam = tff.framework.Lambda(
        'x', tuple_of_federated_types,
        tff.framework.Selection(
            tff.framework.Reference('x', tuple_of_federated_types), index=0))
    zeroth_index_extracted = transformations.zip_selection_as_argument_to_lower_level_lambda(
        lam, [[0]])
    unbound_references = tff.framework.get_map_of_unbound_references(
        zeroth_index_extracted)[zeroth_index_extracted]
    self.assertEmpty(unbound_references)

  def test_binds_single_arg_deep_in_type_tree_to_lower_lambda(self):
    fed_at_clients = tff.FederatedType(tf.int32, tff.CLIENTS)
    fed_at_server = tff.FederatedType(tf.int32, tff.SERVER)
    tuple_of_federated_types = tff.NamedTupleType([[fed_at_clients],
                                                   fed_at_server])
    lam = tff.framework.Lambda(
        'x', tuple_of_federated_types,
        tff.framework.Selection(
            tff.framework.Selection(
                tff.framework.Reference('x', tuple_of_federated_types),
                index=0),
            index=0))
    deep_zeroth_index_extracted = transformations.zip_selection_as_argument_to_lower_level_lambda(
        lam, [[0, 0]])
    self.assertEqual(deep_zeroth_index_extracted.type_signature,
                     lam.type_signature)
    self.assertIsInstance(deep_zeroth_index_extracted, tff.framework.Lambda)
    self.assertIsInstance(deep_zeroth_index_extracted.result,
                          tff.framework.Call)
    self.assertIsInstance(deep_zeroth_index_extracted.result.function,
                          tff.framework.Lambda)
    self.assertEqual(
        str(deep_zeroth_index_extracted.result.function),
        '(_var2 -> federated_map(<(_var3 -> _var3[0]),_var2>))')
    # The below is not clear to me...ah, it makes more sense now...
    self.assertEqual(
        str(deep_zeroth_index_extracted.result.argument),
        'federated_map(<(_var4 -> <_var4>),<_var1[0][0]>[0]>)')

  def test_binds_multiple_args_deep_in_type_tree_to_lower_lambda(self):
    fed_at_clients = tff.FederatedType(tf.int32, tff.CLIENTS)
    fed_at_server = tff.FederatedType(tf.int32, tff.SERVER)
    tuple_of_federated_types = tff.NamedTupleType([[fed_at_clients],
                                                   fed_at_server,
                                                   [fed_at_clients]])
    first_selection = tff.framework.Selection(
        tff.framework.Selection(
            tff.framework.Reference('x', tuple_of_federated_types), index=0),
        index=0)
    second_selection = tff.framework.Selection(
        tff.framework.Selection(
            tff.framework.Reference('x', tuple_of_federated_types), index=2),
        index=0)
    lam = tff.framework.Lambda(
        'x', tuple_of_federated_types,
        tff.framework.Tuple([first_selection, second_selection]))
    deep_zeroth_index_extracted = transformations.zip_selection_as_argument_to_lower_level_lambda(
        lam, [[0, 0], [2, 0]])
    self.assertEqual(deep_zeroth_index_extracted.type_signature,
                     lam.type_signature)
    self.assertIsInstance(deep_zeroth_index_extracted, tff.framework.Lambda)
    self.assertIsInstance(deep_zeroth_index_extracted.result,
                          tff.framework.Call)
    self.assertIsInstance(deep_zeroth_index_extracted.result.function,
                          tff.framework.Lambda)
    self.assertEqual(
        str(deep_zeroth_index_extracted.result.function),
        '(_var2 -> <federated_map(<(_var3 -> _var3[0]),_var2>),'
        'federated_map(<(_var4 -> _var4[1]),_var2>)>)')
    self.assertEqual(
        str(deep_zeroth_index_extracted.result.argument),
        'federated_map(<(_var5 -> <_var5[0],_var5[1]>),federated_map(<(_var6 -> _var6),(let _var7=<_var1[0][0],_var1[2][0]> in federated_zip_at_clients(<_var7[0],_var7[1]>))>)>)'
    )

  def test_binding_multiple_args_results_in_unique_names(self):
    fed_at_clients = tff.FederatedType(tf.int32, tff.CLIENTS)
    fed_at_server = tff.FederatedType(tf.int32, tff.SERVER)
    tuple_of_federated_types = tff.NamedTupleType([[fed_at_clients],
                                                   fed_at_server,
                                                   [fed_at_clients]])
    first_selection = tff.framework.Selection(
        tff.framework.Selection(
            tff.framework.Reference('x', tuple_of_federated_types), index=0),
        index=0)
    second_selection = tff.framework.Selection(
        tff.framework.Selection(
            tff.framework.Reference('x', tuple_of_federated_types), index=2),
        index=0)
    lam = tff.framework.Lambda(
        'x', tuple_of_federated_types,
        tff.framework.Tuple([first_selection, second_selection]))
    deep_zeroth_index_extracted = transformations.zip_selection_as_argument_to_lower_level_lambda(
        lam, [[0, 0], [2, 0]])
    tff.framework.check_has_unique_names(deep_zeroth_index_extracted)


class SelectFederatedOutputFromLambdaTest(absltest.TestCase):

  def test_raises_on_none(self):
    with self.assertRaises(TypeError):
      transformations.select_output_from_lambda(None, 0)

  def test_raises_on_non_lambda(self):
    fed_type = tff.FederatedType(tf.int32, tff.CLIENTS)
    ref = tff.framework.Reference('x', [fed_type])
    with self.assertRaises(TypeError):
      transformations.select_output_from_lambda(ref, 0)

  def test_raises_on_string_indices(self):
    fed_type = tff.FederatedType(tf.int32, tff.CLIENTS)
    ref = tff.framework.Reference('x', [('a', fed_type)])
    lam = tff.framework.Lambda('x', ref.type_signature, ref)
    with self.assertRaises(TypeError):
      transformations.select_output_from_lambda(lam, 'a')

  def test_raises_on_list_of_strings(self):
    fed_type = tff.FederatedType(tf.int32, tff.CLIENTS)
    ref = tff.framework.Reference('x', [[('a', fed_type)]])
    lam = tff.framework.Lambda('x', ref.type_signature, ref)
    with self.assertRaises(TypeError):
      transformations.select_output_from_lambda(lam, ['a'])

  def test_selects_single_federated_output(self):
    fed_at_clients = tff.FederatedType(tf.int32, tff.CLIENTS)
    fed_at_server = tff.FederatedType(tf.int32, tff.SERVER)
    ref = tff.framework.Reference('x', [fed_at_clients, fed_at_server])
    lam = tff.framework.Lambda('x', ref.type_signature, ref)
    zero_selected = transformations.select_output_from_lambda(lam, 0)
    self.assertEqual(zero_selected.type_signature.parameter,
                     lam.type_signature.parameter)
    self.assertEqual(zero_selected.type_signature.result,
                     lam.type_signature.result[0])
    self.assertEqual(str(zero_selected), '(x -> (let _var1=x in _var1[0]))')

  def test_selects_tuple_of_federated_outputs(self):
    fed_at_clients = tff.FederatedType(tf.int32, tff.CLIENTS)
    fed_at_server = tff.FederatedType(tf.int32, tff.SERVER)
    ref = tff.framework.Reference(
        'x', [fed_at_clients, fed_at_clients, fed_at_server])
    lam = tff.framework.Lambda('x', ref.type_signature, ref)
    tuple_selected = transformations.select_output_from_lambda(lam, (0, 1))
    self.assertEqual(tuple_selected.type_signature.parameter,
                     lam.type_signature.parameter)
    self.assertEqual(
        tuple_selected.type_signature.result,
        tff.NamedTupleType(
            [lam.type_signature.result[0], lam.type_signature.result[1]]))
    self.assertEqual(
        str(tuple_selected), '(x -> (let _var1=x in <_var1[0],_var1[1]>))')

  def test_selects_list_of_federated_outputs(self):
    fed_at_clients = tff.FederatedType(tf.int32, tff.CLIENTS)
    fed_at_server = tff.FederatedType(tf.int32, tff.SERVER)
    ref = tff.framework.Reference(
        'x', [fed_at_clients, fed_at_clients, fed_at_server])
    lam = tff.framework.Lambda('x', ref.type_signature, ref)
    tuple_selected = transformations.select_output_from_lambda(lam, [0, 1])
    self.assertEqual(tuple_selected.type_signature.parameter,
                     lam.type_signature.parameter)
    self.assertEqual(
        tuple_selected.type_signature.result,
        tff.NamedTupleType(
            [lam.type_signature.result[0], lam.type_signature.result[1]]))
    self.assertEqual(
        str(tuple_selected), '(x -> (let _var1=x in <_var1[0],_var1[1]>))')

  def test_selects_single_unplaced_output(self):
    ref = tff.framework.Reference('x', [tf.int32, tf.float32, tf.int32])
    lam = tff.framework.Lambda('x', ref.type_signature, ref)
    int_selected = transformations.select_output_from_lambda(lam, 0)
    self.assertEqual(int_selected.type_signature.parameter,
                     lam.type_signature.parameter)
    self.assertEqual(int_selected.type_signature.result,
                     lam.type_signature.result[0])

  def test_selects_multiple_unplaced_outputs(self):
    ref = tff.framework.Reference('x', [tf.int32, tf.float32, tf.int32])
    lam = tff.framework.Lambda('x', ref.type_signature, ref)
    tuple_selected = transformations.select_output_from_lambda(lam, [0, 1])
    self.assertEqual(tuple_selected.type_signature.parameter,
                     lam.type_signature.parameter)
    self.assertEqual(
        tuple_selected.type_signature.result,
        tff.NamedTupleType(
            [lam.type_signature.result[0], lam.type_signature.result[1]]))
    self.assertEqual(
        str(tuple_selected), '(x -> (let _var1=x in <_var1[0],_var1[1]>))')


class ConcatenateFunctionOutputsTest(absltest.TestCase):

  def test_raises_on_non_lambda_args(self):
    reference = tff.framework.Reference('x', tf.int32)
    tff_lambda = tff.framework.Lambda('x', tf.int32, reference)
    with self.assertRaises(TypeError):
      transformations.concatenate_function_outputs(tff_lambda, reference)
    with self.assertRaises(TypeError):
      transformations.concatenate_function_outputs(reference, tff_lambda)

  def test_raises_on_non_unique_names(self):
    reference = tff.framework.Reference('x', tf.int32)
    good_lambda = tff.framework.Lambda('x', tf.int32, reference)
    bad_lambda = tff.framework.Lambda('x', tf.int32, good_lambda)
    with self.assertRaises(ValueError):
      transformations.concatenate_function_outputs(good_lambda, bad_lambda)
    with self.assertRaises(ValueError):
      transformations.concatenate_function_outputs(bad_lambda, good_lambda)

  def test_raises_on_different_parameter_types(self):
    int_reference = tff.framework.Reference('x', tf.int32)
    int_lambda = tff.framework.Lambda('x', tf.int32, int_reference)
    float_reference = tff.framework.Reference('x', tf.float32)
    float_lambda = tff.framework.Lambda('x', tf.float32, float_reference)
    with self.assertRaises(TypeError):
      transformations.concatenate_function_outputs(int_lambda, float_lambda)

  def test_parameters_are_mapped_together(self):
    x_reference = tff.framework.Reference('x', tf.int32)
    x_lambda = tff.framework.Lambda('x', tf.int32, x_reference)
    y_reference = tff.framework.Reference('y', tf.int32)
    y_lambda = tff.framework.Lambda('y', tf.int32, y_reference)
    concatenated = transformations.concatenate_function_outputs(
        x_lambda, y_lambda)
    parameter_name = concatenated.parameter_name

    def _raise_on_other_name_reference(comp):
      if isinstance(comp,
                    tff.framework.Reference) and comp.name != parameter_name:
        raise ValueError
      return comp, True

    tff.framework.check_has_unique_names(concatenated)
    tff.framework.transform_postorder(concatenated,
                                      _raise_on_other_name_reference)

  def test_concatenates_identities(self):
    x_reference = tff.framework.Reference('x', tf.int32)
    x_lambda = tff.framework.Lambda('x', tf.int32, x_reference)
    y_reference = tff.framework.Reference('y', tf.int32)
    y_lambda = tff.framework.Lambda('y', tf.int32, y_reference)
    concatenated = transformations.concatenate_function_outputs(
        x_lambda, y_lambda)
    self.assertEqual(str(concatenated), '(_var1 -> <_var1,_var1>)')


class NormalizedBitTest(absltest.TestCase):

  def test_raises_on_none(self):
    with self.assertRaises(TypeError):
      transformations.normalize_all_equal_bit(None)

  def test_converts_all_equal_at_clients_reference_to_not_equal(self):
    fed_type_all_equal = tff.FederatedType(
        tf.int32, tff.CLIENTS, all_equal=True)
    normalized_comp = transformations.normalize_all_equal_bit(
        tff.framework.Reference('x', fed_type_all_equal))
    self.assertEqual(normalized_comp.type_signature,
                     tff.FederatedType(tf.int32, tff.CLIENTS, all_equal=False))
    self.assertIsInstance(normalized_comp, tff.framework.Reference)
    self.assertEqual(str(normalized_comp), 'x')

  def test_converts_not_all_equal_at_server_reference_to_equal(self):
    fed_type_not_all_equal = tff.FederatedType(
        tf.int32, tff.SERVER, all_equal=False)
    normalized_comp = transformations.normalize_all_equal_bit(
        tff.framework.Reference('x', fed_type_not_all_equal))
    self.assertEqual(normalized_comp.type_signature,
                     tff.FederatedType(tf.int32, tff.SERVER, all_equal=True))
    self.assertIsInstance(normalized_comp, tff.framework.Reference)
    self.assertEqual(str(normalized_comp), 'x')

  def test_converts_all_equal_at_clients_lambda_parameter_to_not_equal(self):
    fed_type_all_equal = tff.FederatedType(
        tf.int32, tff.CLIENTS, all_equal=True)
    normalized_fed_type = tff.FederatedType(tf.int32, tff.CLIENTS)
    ref = tff.framework.Reference('x', fed_type_all_equal)
    lam = tff.framework.Lambda('x', fed_type_all_equal, ref)
    normalized_lambda = transformations.normalize_all_equal_bit(lam)
    self.assertEqual(lam.type_signature,
                     tff.FunctionType(fed_type_all_equal, fed_type_all_equal))
    self.assertIsInstance(normalized_lambda, tff.framework.Lambda)
    self.assertEqual(str(normalized_lambda), '(x -> x)')
    self.assertEqual(normalized_lambda.type_signature,
                     tff.FunctionType(normalized_fed_type, normalized_fed_type))

  def test_converts_not_all_equal_at_server_lambda_parameter_to_equal(self):
    fed_type_not_all_equal = tff.FederatedType(
        tf.int32, tff.SERVER, all_equal=False)
    normalized_fed_type = tff.FederatedType(tf.int32, tff.SERVER)
    ref = tff.framework.Reference('x', fed_type_not_all_equal)
    lam = tff.framework.Lambda('x', fed_type_not_all_equal, ref)
    normalized_lambda = transformations.normalize_all_equal_bit(lam)
    self.assertEqual(
        lam.type_signature,
        tff.FunctionType(fed_type_not_all_equal, fed_type_not_all_equal))
    self.assertIsInstance(normalized_lambda, tff.framework.Lambda)
    self.assertEqual(str(normalized_lambda), '(x -> x)')
    self.assertEqual(normalized_lambda.type_signature,
                     tff.FunctionType(normalized_fed_type, normalized_fed_type))

  def test_converts_federated_map_all_equal_to_federated_map(self):
    fed_type_all_equal = tff.FederatedType(
        tf.int32, tff.CLIENTS, all_equal=True)
    normalized_fed_type = tff.FederatedType(tf.int32, tff.CLIENTS)
    int_ref = tff.framework.Reference('x', tf.int32)
    int_identity = tff.framework.Lambda('x', tf.int32, int_ref)
    federated_int_ref = tff.framework.Reference('y', fed_type_all_equal)
    called_federated_map_all_equal = tff.framework.create_federated_map_all_equal(
        int_identity, federated_int_ref)
    normalized_federated_map = transformations.normalize_all_equal_bit(
        called_federated_map_all_equal)
    self.assertEqual(called_federated_map_all_equal.function.uri,
                     tff.framework.FEDERATED_MAP_ALL_EQUAL.uri)
    self.assertIsInstance(normalized_federated_map, tff.framework.Call)
    self.assertIsInstance(normalized_federated_map.function,
                          tff.framework.Intrinsic)
    self.assertEqual(normalized_federated_map.function.uri,
                     tff.framework.FEDERATED_MAP.uri)
    self.assertEqual(normalized_federated_map.type_signature,
                     normalized_fed_type)


if __name__ == '__main__':
  tf.enable_v2_behavior()
  absltest.main()