"""
A/B Testing Framework for Intelligent Sports News Assistant.
So sánh hiệu quả giữa các phiên bản prompt, model, và tham số AI.
"""

from tests.ab_testing.experiment import ABExperiment, ExperimentResult
from tests.ab_testing.variants import PromptVariant, ModelVariant
from tests.ab_testing.evaluator import OutputEvaluator

__all__ = [
    "ABExperiment",
    "ExperimentResult",
    "PromptVariant",
    "ModelVariant",
    "OutputEvaluator",
]
