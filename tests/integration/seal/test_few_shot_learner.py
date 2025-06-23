"""Tests for the FewShotLearner class with mock models."""

import sys
import os
import pytest
import torch
from pathlib import Path
from unittest.mock import patch, MagicMock, ANY, DEFAULT

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

# Create a mock model class
class MockModule(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.linear = torch.nn.Linear(10, 10)

class MockAttention(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.q_proj = torch.nn.Linear(768, 768)
        self.v_proj = torch.nn.Linear(768, 768)
        self.k_proj = torch.nn.Linear(768, 768)
        self.o_proj = torch.nn.Linear(768, 768)

class MockMLP(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.gate_proj = torch.nn.Linear(768, 3072)
        self.up_proj = torch.nn.Linear(768, 3072)
        self.down_proj = torch.nn.Linear(3072, 768)

class MockDecoderLayer(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.self_attn = MockAttention()
        self.mlp = MockMLP()
        self.input_layernorm = torch.nn.LayerNorm(768)
        self.post_attention_layernorm = torch.nn.LayerNorm(768)

class GenerationConfig:
    def __init__(self):
        self.max_length = 20
        self.max_new_tokens = 20
        self.do_sample = True
        self.temperature = 0.7
        self.top_p = 0.9
        self.eos_token_id = 1
        self.pad_token_id = 0

class MockModel(torch.nn.Module):
    def __init__(self, *args, **kwargs):
        super().__init__()
        # Create a simple config
        self.config = MagicMock()
        self.config.pad_token_id = 0
        self.config.eos_token_id = 1
        self.config.hidden_size = 768
        self.config.num_hidden_layers = 1
        self.config.num_attention_heads = 1
        self.config.num_key_value_heads = 1
        self.config.hidden_act = "gelu"
        self.config.intermediate_size = 4
        self.config.rms_norm_eps = 1e-5
        self.config.vocab_size = 50257  # GPT-2 vocab size
        self.config.tie_word_embeddings = True
        self.config.model_type = "gpt2"
        self.config.torch_dtype = torch.float32
        self.config.to_dict.return_value = {"model_type": "gpt2"}
        
        # Set up device
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # PEFT compatibility
        self.base_model = self
        self.peft_config = {}
        self.disable_adapter = MagicMock(return_value=self)
        self.enable_adapter = MagicMock(return_value=self)
        
        # Required for generation
        self.generation_config = MagicMock()
        self.generation_config.max_length = 100
        
    @property
    def device(self):
        return self._device
        
    @device.setter
    def device(self, value):
        if isinstance(value, str):
            self._device = torch.device(value)
        else:
            self._device = value
    
    def to(self, *args, **kwargs):
        # Handle device movement
        if len(args) > 0 and (isinstance(args[0], (str, torch.device)) or 
                            (hasattr(args[0], 'type') and args[0].type != '')):
            self.device = args[0]
        elif 'device' in kwargs:
            self.device = kwargs['device']
        return self
    
    def __call__(self, *args, **kwargs):
        # For forward pass, return logits with shape [batch, seq_len, vocab_size]
        input_ids = kwargs.get('input_ids', torch.tensor([[1, 2, 3, 4, 5]]))
        batch_size, seq_len = input_ids.shape
        return {"logits": torch.randn(batch_size, seq_len, 50257, device=self.device)}
    
    def forward(self, *args, **kwargs):
        return self.__call__(*args, **kwargs)
    
    def prepare_inputs_for_generation(self, input_ids, **kwargs):
        return {"input_ids": input_ids}
    
    def generate(self, input_ids, **kwargs):
        # Return fixed-length dummy output
        return torch.ones((input_ids.shape[0], 10), dtype=torch.long, device=self.device)

# Create a mock tokenizer class
class TokenizerOutput(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.device = None
        
    def to(self, device):
        self.device = device
        # Return self to allow chaining
        return self

class MockTokenizer:
    def __init__(self):
        # Initialize with default values
        self._pad_token = "<pad>"
        self._eos_token = "</s>"
        self.pad_token_id = 0
        self.eos_token_id = 1
        self.padding_side = "left"
        self.model_input_names = ["input_ids", "attention_mask"]
        self.model_max_length = 4096
        
        # Mock methods
        self.encode = MagicMock(return_value=[1, 2, 3, 4, 5])
    
    def decode(self, *args, **kwargs):
        # Return a mock response when decode is called
        return "Mocked response"
    
    def __call__(self, *args, **kwargs):
        # Create tensors for input_ids and attention_mask
        input_ids = torch.tensor([[1, 2, 3, 4, 5]])
        attention_mask = torch.tensor([[1, 1, 1, 1, 1]])
        
        # Create a custom class that has a to() method and supports ** unpacking
        class TokenizerOutput(dict):
            def __init__(self, data):
                super().__init__(data)
                self.update(data)
                
            def to(self, *args, **kwargs):
                # Return self to simulate device movement
                return self
                
            def __getattr__(self, key):
                # Allow attribute access for dictionary keys
                try:
                    return self[key]
                except KeyError:
                    raise AttributeError(f"'TokenizerOutput' object has no attribute '{key}'") from None
                    
            def __setattr__(self, key, value):
                # Allow attribute assignment to work with dictionary
                self[key] = value
                
            def __contains__(self, key):
                # Support 'in' operator
                return super().__contains__(key)
                
            def get(self, key, default=None):
                # Support .get() method
                return super().get(key, default)
        
        # Create the result dictionary
        result = {
            "input_ids": input_ids,
            "attention_mask": attention_mask
        }
        
        # If return_tensors is specified, return a TokenizerOutput object
        if kwargs.get("return_tensors") == "pt":
            return TokenizerOutput(result)
            
        return result
    
    @property
    def pad_token(self):
        return self._pad_token
        
    @pad_token.setter
    def pad_token(self, value):
        self._pad_token = value
        # When pad_token is set, also update pad_token_id if not set
        if not hasattr(self, 'pad_token_id') or self.pad_token_id is None:
            self.pad_token_id = 0
            
    @property
    def eos_token(self):
        return self._eos_token
        
    @eos_token.setter
    def eos_token(self, value):
        self._eos_token = value
        # When eos_token is set, also update eos_token_id if not set
        if not hasattr(self, 'eos_token_id') or self.eos_token_id is None:
            self.eos_token_id = 1
        
    @property
    def eos_token(self):
        return self._eos_token
        
    @eos_token.setter
    def eos_token(self, value):
        self._eos_token = value
        
    def __call__(self, *args, **kwargs):
        # Create tensors for input_ids and attention_mask
        input_ids = torch.tensor([[1, 2, 3, 4, 5]])
        attention_mask = torch.tensor([[1, 1, 1, 1, 1]])
        
        # Create a custom class that has a to() method and supports ** unpacking
        class TokenizerOutput(dict):
            def __init__(self, data):
                super().__init__(data)
                self.update(data)
                
            def to(self, *args, **kwargs):
                # Return self to simulate device movement
                return self
                
            def __getattr__(self, key):
                # Allow attribute access for dictionary keys
                try:
                    return self[key]
                except KeyError:
                    raise AttributeError(f"'TokenizerOutput' object has no attribute '{key}'") from None
                    
            def __setattr__(self, key, value):
                # Allow attribute assignment to work with dictionary
                self[key] = value
                
            def __contains__(self, key):
                # Support 'in' operator
                return super().__contains__(key)
                
            def get(self, key, default=None):
                # Support .get() method
                return super().get(key, default)
        
        # Create the result dictionary
        result = {
            "input_ids": input_ids,
            "attention_mask": attention_mask
        }
        
        # If return_tensors is specified, return a TokenizerOutput object
        if kwargs.get("return_tensors") == "pt":
            return TokenizerOutput(result)
            
        return result
        
    def to(self, *args, **kwargs):
        # Return self to simulate device movement
        return self

# Patch the transformers imports at the module level
with patch('transformers.AutoModelForCausalLM.from_pretrained', return_value=MockModel()), \
     patch('transformers.AutoTokenizer.from_pretrained', return_value=MockTokenizer()):
    from evoseal.integration.seal.few_shot.few_shot_learner import FewShotLearner, FewShotExample

# Test data
TEST_EXAMPLES = [
    FewShotExample(
        input_data="What is the capital of France?",
        output_data="The capital of France is Paris.",
        metadata={"source": "test", "difficulty": "easy"}
    ),
    FewShotExample(
        input_data="Who wrote 'Romeo and Juliet'?",
        output_data="William Shakespeare wrote 'Romeo and Juliet'.",
        metadata={"source": "test", "difficulty": "easy"}
    ),
]


def test_few_shot_learner_initialization():
    """Test that FewShotLearner initializes correctly with mock model."""
    # Import inside the test to avoid circular imports
    from evoseal.integration.seal.few_shot.few_shot_learner import FewShotLearner
    
    # Create a minimal mock model that won't cause recursion
    class MockPEFTModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            # Initialize device string first
            self._device_str = "cuda" if torch.cuda.is_available() else "cpu"
            
            # Minimal config
            self.config = MagicMock()
            self.config.model_type = "llama"
            self.config.torch_dtype = torch.float32
            self.config.to_dict.return_value = {"model_type": "llama"}
            self.config.pad_token_id = 0
            self.config.eos_token_id = 1
            
            # Model structure with required target modules for PEFT
            self.model = torch.nn.Module()
            
            # Add a transformer layer with the required attention modules
            class MockTransformerLayer(torch.nn.Module):
                def __init__(self):
                    super().__init__()
                    self.self_attn = torch.nn.Module()
                    self.self_attn.q_proj = torch.nn.Linear(1, 1)  # Required target module
                    self.self_attn.v_proj = torch.nn.Linear(1, 1)  # Required target module
                    
            # Add a single transformer layer
            self.model.layers = torch.nn.ModuleList([MockTransformerLayer()])
            
            # PEFT specific attributes
            self.peft_config = {}
            self.base_model = self
            self.disable_adapter = MagicMock(return_value=self)
            self.enable_adapter = MagicMock(return_value=self)
            
            # Generation config
            self.generation_config = MagicMock()
            self.generation_config.max_length = 100
            self.generation_config.do_sample = False
            self.generation_config.num_beams = 1
            
            # Required for PEFT
            self.is_loaded_in_8bit = False
            self.is_loaded_in_4bit = False
            self.is_peft_model = True
            
        # Device property with getter and setter
        @property
        def device(self):
            return torch.device(self._device_str)
            
        @device.setter
        def device(self, value):
            self._device_str = str(value)
            
        # Implement _apply to prevent recursion and handle device movement
        def _apply(self, fn, *args, **kwargs):
            # Don't apply the function to the entire module tree to prevent recursion
            # Just update the device string if needed
            device = None
            if 'device' in kwargs:
                device = kwargs['device']
            elif args and (isinstance(args[0], (str, torch.device)) or hasattr(args[0], 'type')):
                device = args[0]
                
            if device is not None:
                self._device_str = str(device)
                
            # Update dtype if needed
            if 'dtype' in kwargs:
                self.dtype = kwargs['dtype']
                
            return self
            
        # to() implementation that uses our custom _apply
        def to(self, *args, **kwargs):
            self._apply(None, *args, **kwargs)
            return self
            
        def prepare_inputs_for_generation(self, input_ids, **kwargs):
            return {"input_ids": input_ids, "attention_mask": torch.ones_like(input_ids)}
            
        def forward(self, *args, **kwargs):
            input_ids = kwargs.get('input_ids', torch.tensor([[1, 2, 3, 4, 5]]))
            if not isinstance(input_ids, torch.Tensor):
                input_ids = torch.tensor(input_ids)
            batch_size, seq_len = input_ids.shape
            return {"logits": torch.randn(batch_size, seq_len, 50257)}
            
        def generate(self, input_ids=None, **kwargs):
            # Handle case where input_ids is passed as a dictionary
            if isinstance(input_ids, dict):
                input_ids = input_ids.get('input_ids', torch.tensor([[1, 2, 3, 4, 5]]))
            
            # Handle case where input_ids is not provided (comes from kwargs)
            if input_ids is None and 'input_ids' in kwargs:
                input_ids = kwargs['input_ids']
            
            # Ensure input_ids is a tensor
            if not isinstance(input_ids, torch.Tensor):
                input_ids = torch.tensor(input_ids)
                
            # Return a tensor of shape (batch_size, 10) with ones
            return torch.ones((input_ids.shape[0], 10), dtype=torch.long)
            
        def __call__(self, *args, **kwargs):
            return self.forward(*args, **kwargs)
        
        def print_trainable_parameters(self):
            # Simulate the output of print_trainable_parameters
            trainable_params = 16
            all_params = 20
            trainable_percent = 80.0
            print(f"trainable params: {trainable_params} || all params: {all_params} || trainable%: {trainable_percent:.4f}")
            return {
                "trainable_params": trainable_params,
                "all_params": all_params,
                "trainable_percent": trainable_percent
            }
    
    # Create mock model and tokenizer
    mock_model = MockPEFTModel()
    mock_tokenizer = MockTokenizer()
    
    # Create a mock for get_peft_model that just returns the model
    def mock_get_peft_model(model, config):
        # Set peft_config on the model to simulate PEFT model
        model.peft_config = {
            'default': {
                'r': config.r,
                'lora_alpha': config.lora_alpha,
                'lora_dropout': config.lora_dropout,
                'bias': config.bias,
                'task_type': config.task_type,
                'target_modules': config.target_modules
            }
        }
        return model
    
    # Patch the necessary functions - use the full import path from the module being tested
    with patch('transformers.AutoModelForCausalLM.from_pretrained', return_value=mock_model) as mock_model_load, \
         patch('transformers.AutoTokenizer.from_pretrained', return_value=mock_tokenizer) as mock_tokenizer_load, \
         patch('evoseal.integration.seal.few_shot.few_shot_learner.get_peft_model', side_effect=mock_get_peft_model) as mock_get_peft_model:
        
        # Initialize the learner
        learner = FewShotLearner(
            base_model_name="gpt2",
            lora_rank=4,
            lora_alpha=16,
            lora_dropout=0.1
        )
        
        # Verify initial state
        assert learner.examples == []
        assert not learner.is_initialized
        assert learner.lora_config["r"] == 4
        assert learner.lora_config["lora_alpha"] == 16
        assert learner.lora_config["lora_dropout"] == 0.1

        # Model and tokenizer should not be loaded yet (lazy loading)
        mock_model_load.assert_not_called()
        mock_tokenizer_load.assert_not_called()
        mock_get_peft_model.assert_not_called()

        # Now trigger model initialization by calling a method that requires it
        response = learner.generate("test query")
        
        # Verify the response is a string (from our mock)
        assert isinstance(response, str)
        
        # Now verify the model and tokenizer were loaded with correct args
        mock_model_load.assert_called_once()
        
        # Verify tokenizer was loaded with expected arguments
        mock_tokenizer_load.assert_called_once()
        call_args, call_kwargs = mock_tokenizer_load.call_args
        # The model name is the first positional argument
        assert call_args[0] == "gpt2"
        # Check keyword arguments
        assert call_kwargs.get('padding_side') == "left"
        assert 'cache_dir' in call_kwargs
        
        # Verify get_peft_model was called with the correct parameters
        mock_get_peft_model.assert_called_once()
        
        # Get the config passed to get_peft_model
        peft_call_args, _ = mock_get_peft_model.call_args
        assert peft_call_args[0] == mock_model
        peft_config = peft_call_args[1]  # Config is the second argument
        
        # Verify the config has the correct values
        assert peft_config.r == 4
        assert peft_config.lora_alpha == 16
        assert peft_config.lora_dropout == 0.1
        assert peft_config.bias == "none"
        assert peft_config.task_type == "CAUSAL_LM"
        assert set(peft_config.target_modules) == {"q_proj", "v_proj"}
        
        # Verify tokenizer settings were updated
        # The pad_token should only be set to eos_token if pad_token was not set
        # In our MockTokenizer, we set pad_token to "<pad>" in __init__
        # So it should remain "<pad>" and not be changed to eos_token
        assert mock_tokenizer.pad_token == "<pad>"  # Should remain as initialized
        assert mock_tokenizer.eos_token == "</s>"  # eos_token should remain unchanged
        assert mock_tokenizer.padding_side == "left"
        
        # Verify the model is marked as initialized
        assert learner.is_initialized


def test_add_and_remove_examples():
    """Test adding and removing examples with mock model."""
    with patch('transformers.AutoModelForCausalLM.from_pretrained', return_value=MockModel()), \
         patch('transformers.AutoTokenizer.from_pretrained', return_value=MockTokenizer()):
        
        learner = FewShotLearner()
        
        # Add examples
        for example in TEST_EXAMPLES:
            learner.add_example(example)
        
        assert len(learner.examples) == 2
        assert learner.examples[0].input_data == "What is the capital of France?"
        
        # Remove an example
        learner.remove_example(0)
        assert len(learner.examples) == 1
        assert "Romeo and Juliet" in learner.examples[0].output_data
        
        # Test removing with invalid index
        with pytest.raises(IndexError):
            learner.remove_example(10)


def test_clear_examples():
    """Test clearing all examples with mock model."""
    with patch('transformers.AutoModelForCausalLM.from_pretrained', return_value=MockModel()), \
         patch('transformers.AutoTokenizer.from_pretrained', return_value=MockTokenizer()):
        
        learner = FewShotLearner()
        
        for example in TEST_EXAMPLES:
            learner.add_example(example)
        
        assert len(learner.examples) == 2
        learner.clear_examples()
        assert len(learner.examples) == 0


def test_get_relevant_examples():
    """Test retrieving relevant examples with mock model."""
    with patch('transformers.AutoModelForCausalLM.from_pretrained', return_value=MockModel()), \
         patch('transformers.AutoTokenizer.from_pretrained', return_value=MockTokenizer()):
        
        learner = FewShotLearner()
        
        for example in TEST_EXAMPLES:
            learner.add_example(example)
        
        # Default behavior should return first k examples
        examples = learner.get_relevant_examples("test query", k=1)
        assert len(examples) == 1
        assert "capital of France" in examples[0].output_data


def test_format_prompt():
    """Test prompt formatting with mock model."""
    with patch('transformers.AutoModelForCausalLM.from_pretrained', return_value=MockModel()), \
         patch('transformers.AutoTokenizer.from_pretrained', return_value=MockTokenizer()):
        
        learner = FewShotLearner()
        learner.add_example(TEST_EXAMPLES[0])
        
        # Test format prompt
        prompt = learner.format_prompt("What is the capital of Spain?")
        assert isinstance(prompt, str)
        assert "What is the capital of France?" in prompt
        assert "What is the capital of Spain?" in prompt


def test_model_generation():
    """Test model generation with mocked model and tokenizer."""
    with patch('transformers.AutoModelForCausalLM.from_pretrained', return_value=MockModel()) as mock_model, \
         patch('transformers.AutoTokenizer.from_pretrained', return_value=MockTokenizer()) as mock_tokenizer:
        
        # Initialize learner and generate
        learner = FewShotLearner()
        for example in TEST_EXAMPLES:
            learner.add_example(example)
        
        response = learner.generate("Test query", max_new_tokens=10)
        
        # Verify response
        assert response == "Generated response"
        
        # Verify tokenizer and model were called
        assert mock_model.called
        assert mock_tokenizer.called


def test_save_and_load_examples(tmp_path):
    """Test saving and loading examples to/from disk with mock model."""
    with patch('transformers.AutoModelForCausalLM.from_pretrained', return_value=MockModel()), \
         patch('transformers.AutoTokenizer.from_pretrained', return_value=MockTokenizer()):
        
        learner = FewShotLearner()
        
        for example in TEST_EXAMPLES:
            learner.add_example(example)
        
        # Save examples
        save_path = tmp_path / "test_examples.json"
        learner.save_examples(save_path)
        
        # Load examples (this is a static method, doesn't need instance)
        loaded_examples = FewShotLearner.load_examples(save_path)
        
        # Verify loaded examples
        assert len(loaded_examples) == 2
        assert loaded_examples[0].input_data == "What is the capital of France?"
        assert loaded_examples[1].output_data == "William Shakespeare wrote 'Romeo and Juliet'."
        assert loaded_examples[0].metadata["source"] == "test"


def test_fine_tune(tmp_path):
    """Test fine-tuning with mocked components."""
    with patch('transformers.Trainer') as mock_trainer, \
         patch('transformers.AutoModelForCausalLM.from_pretrained', return_value=MockModel()), \
         patch('transformers.AutoTokenizer.from_pretrained', return_value=MockTokenizer()):
        
        # Mock trainer
        mock_trainer.return_value.train.return_value = None
        mock_trainer.return_value.save_model.return_value = None
        
        # Initialize learner and fine-tune
        learner = FewShotLearner()
        for example in TEST_EXAMPLES:
            learner.add_example(example)
        
        output_dir = tmp_path / "output"
        learner.fine_tune(
            output_dir=output_dir,
            num_epochs=1,
            per_device_train_batch_size=1,
            learning_rate=1e-5
        )
        
        # Verify trainer was called
        assert mock_trainer.return_value.train.called
        assert mock_trainer.return_value.save_model.called
        
        # Verify output directory exists
        assert output_dir.exists()


def test_load_pretrained():
    """Test loading a pretrained model with mocks."""
    # Create a mock model and tokenizer
    mock_model = MockModel()
    mock_tokenizer = MockTokenizer()
    
    with patch('transformers.AutoModelForCausalLM.from_pretrained', return_value=mock_model) as mock_model_load, \
         patch('transformers.AutoTokenizer.from_pretrained', return_value=mock_tokenizer) as mock_tokenizer_load, \
         patch('peft.PeftModel.from_pretrained') as mock_peft_load:
        
        # Mock the PeftModel.from_pretrained to return our mock model
        mock_peft_load.return_value = mock_model
        
        # Import here to avoid circular imports
        from evoseal.integration.seal.few_shot.few_shot_learner import FewShotLearner
        
        # Mock the class to return a new instance
        with patch.object(FewShotLearner, '__new__') as mock_new:
            # Create a mock instance
            mock_instance = MagicMock()
            mock_new.return_value = mock_instance
            
            # Call the class method
            model_path = "test/path/to/model"
            result = FewShotLearner.load_pretrained(model_path)
            
            # Verify the result is our mock instance
            assert result is mock_instance
            
            # Verify model and tokenizer were loaded
            mock_model_load.assert_called_once()
            mock_tokenizer_load.assert_called_once()
            mock_peft_load.assert_called_once()
            
            # Verify the tokenizer's pad token is set correctly
            assert mock_tokenizer.pad_token == "</s>"  # Should be set to eos_token
