"""
Logging Example for EVOSEAL

This example demonstrates the key features of the EVOSEAL logging system,
including structured logging, context tracking, and performance monitoring.
"""
import time
import random
from pathlib import Path
from evoseal.utils.logging import (
    setup_logging,
    LoggingMixin,
    with_request_id,
    log_execution_time
)

# Initialize logging
logger = setup_logging()

class DataProcessor(LoggingMixin):
    """Example class demonstrating the LoggingMixin and performance monitoring."""
    
    def __init__(self, name: str):
        super().__init__()
        self.name = name
        self.logger.info(f"Initialized DataProcessor: {name}")
    
    @log_execution_time(logger)
    def process_data(self, data: list) -> dict:
        """Process data and log performance metrics."""
        self.logger.info("Starting data processing", extra={"data_size": len(data)})
        
        # Simulate processing time
        processing_time = random.uniform(0.1, 0.5)
        time.sleep(processing_time)
        
        # Log performance metric
        self.log_performance("processing_time_ms", 
                           processing_time * 1000,
                           operation="data_processing",
                           data_size=len(data))
        
        # Simulate occasional errors
        if random.random() < 0.2:
            try:
                raise ValueError("Random error occurred during processing")
            except ValueError as e:
                self.logger.error("Error processing data", exc_info=True)
                raise
                
        return {"status": "success", "items_processed": len(data)}

@with_request_id(logger)
def handle_request(user_id: str, data: list):
    """Example function demonstrating request context and error handling."""
    logger.info("Handling request", extra={"user_id": user_id, "data_size": len(data)})
    
    processor = DataProcessor(f"processor-{user_id}")
    
    try:
        result = processor.process_data(data)
        logger.info("Request completed successfully", 
                   extra={"result": result})
        return result
    except Exception as e:
        logger.critical("Request failed", 
                       extra={"error": str(e), "user_id": user_id},
                       exc_info=True)
        raise

def main():
    """Run the logging example."""
    logger.info("Starting logging example")
    
    # Create test data
    test_data = [i for i in range(10)]
    
    # Process multiple requests
    for i in range(5):
        user_id = f"user_{i+1}"
        logger.debug(f"Processing request for {user_id}")
        
        try:
            result = handle_request(user_id, test_data)
            print(f"Request {i+1} result: {result}")
        except Exception as e:
            print(f"Request {i+1} failed: {e}")
        
        # Add a small delay between requests
        time.sleep(0.5)
    
    logger.info("Logging example completed")

if __name__ == "__main__":
    # Ensure logs directory exists
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    main()
