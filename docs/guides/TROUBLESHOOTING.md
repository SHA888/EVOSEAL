# Troubleshooting Guide

This guide provides solutions to common issues you might encounter while using or developing EVOSEAL.

## Table of Contents

- [Installation Issues](#installation-issues)
- [Runtime Errors](#runtime-errors)
- [Performance Problems](#performance-problems)
- [Model-Related Issues](#model-related-issues)
- [Common Error Messages](#common-error-messages)
- [Debugging Tips](#debugging-tips)
- [Getting Help](#getting-help)

## Installation Issues

### 1. Dependency Conflicts

**Symptoms**:
- `pip install` fails with version conflicts
- Import errors after installation

**Solutions**:
1. Create a fresh virtual environment:
   ```bash
   python -m venv venv
   source .venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. If using conda:
   ```bash
   conda create -n evoseal python=3.10
   conda activate evoseal
   pip install -r requirements.txt
   ```

### 2. Missing System Dependencies

**Symptoms**:
- Build failures during package installation
- Missing header files

**Solutions**:
- On Ubuntu/Debian:
  ```bash
  sudo apt-get update
  sudo apt-get install python3-dev python3-venv build-essential
  ```

- On macOS:
  ```bash
  xcode-select --install
  brew install python-tk
  ```

## Runtime Errors

### 1. API Key Not Found

**Error**: `API key not found`

**Solution**:
1. Set the API key as an environment variable:
   ```bash
   export OPENAI_API_KEY='your-api-key'  # pragma: allowlist secret
   export ANTHROPIC_API_KEY='your-api-key'  # pragma: allowlist secret
   ```

2. Or use a `.env` file in your project root:
   ```
   OPENAI_API_KEY=your-api-key
   ANTHROPIC_API_KEY=your-api-key
   ```

### 2. CUDA Out of Memory

**Error**: `CUDA out of memory`

**Solutions**:
1. Reduce batch size in configuration
2. Use a smaller model
3. Enable gradient checkpointing
4. Use CPU instead of GPU:
   ```python
   import os
   os.environ['CUDA_VISIBLE_DEVICES'] = ''
   ```

## Performance Problems

### 1. Slow Evolution

**Possible Causes**:
- Large population size
- Complex fitness functions
- Network latency for API calls

**Solutions**:
1. Reduce population size
2. Optimize fitness functions
3. Enable caching:
   ```python
   from functools import lru_cache

   @lru_cache(maxsize=128)
   def expensive_function(x):
       # ...
   ```

### 2. High Memory Usage

**Solutions**:
1. Clear unused variables:
   ```python
   import gc
   gc.collect()
   ```

2. Use generators instead of lists
3. Process data in smaller batches

## Model-Related Issues

### 1. Poor Quality Output

**Solutions**:
1. Adjust temperature and other generation parameters
2. Provide more specific prompts
3. Use few-shot examples
4. Try a different model

### 2. Rate Limiting

**Error**: `Rate limit exceeded`

**Solutions**:
1. Add delays between requests:
   ```python
   import time
   time.sleep(1)  # 1 second delay
   ```

2. Implement exponential backoff:
   ```python
   import time
   import random

   def exponential_backoff(retries):
       base_delay = 1  # seconds
       max_delay = 60  # seconds
       delay = min(max_delay, (2 ** retries) * base_delay + random.uniform(0, 1))
       time.sleep(delay)
   ```

## Common Error Messages

### 1. `ModuleNotFoundError: No module named 'evoseal'`

**Solution**:
1. Install the package in development mode:
   ```bash
   pip install -e .
   ```

### 2. `TypeError: 'X' object is not callable`

**Solution**:
- Check for variable name conflicts
- Verify function signatures
- Ensure all required parameters are provided

## Debugging Tips

### 1. Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 2. Use pdb for Debugging

```python
import pdb; pdb.set_trace()  # Add this line where you want to start debugging
```

### 3. Check Intermediate Results

```python
# Print intermediate results
def fitness_function(individual):
    print(f"Evaluating: {individual}")
    # ...
```

## Getting Help

If you've tried the solutions above and are still experiencing issues:

1. **Check the Documentation**: [https://sha888.github.io/EVOSEAL/](https://sha888.github.io/EVOSEAL/)
2. **Search Issues**: [GitHub Issues](https://github.com/SHA888/EVOSEAL/issues)
3. **Open a New Issue**:
   - Include error messages and stack traces
   - Describe what you were trying to do
   - Provide a minimal reproducible example
   - Include your environment details:
     ```
     - OS: [e.g., Ubuntu 20.04]
     - Python version: [e.g., 3.10.0]
     - EVOSEAL version: [e.g., 0.1.0]
     ```

## Known Issues

1. **Memory Leaks**
   - Some operations may cause memory leaks in long-running processes
   - Workaround: Restart the process periodically

2. **Inconsistent Behavior**
   - Due to the stochastic nature of evolution, results may vary between runs
   - Set random seeds for reproducibility:
     ```python
     import random
     import numpy as np
     import torch

     random.seed(42)
     np.random.seed(42)
     torch.manual_seed(42)
     ```
