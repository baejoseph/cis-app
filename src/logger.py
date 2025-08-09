import logging
import os
from datetime import datetime
import boto3
from helpers import load_config
from botocore.exceptions import ClientError

def setup_logger(name: str = "rag-lite", s3_bucket: str = None, s3_prefix: str = 'logs/'):
    logger = logging.getLogger(name)
    if not logger.handlers:  # Avoid adding handlers multiple times
        logger.setLevel(logging.INFO)
        
        # Console handler (keeps real-time output, goes to CloudWatch in ECS)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Format
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        if s3_bucket:
            # Custom S3 handler
            class S3Handler(logging.Handler):
                def __init__(self, bucket, prefix):
                    super().__init__()
                    self.bucket = bucket
                    self.prefix = prefix
                    self.s3 = boto3.client('s3')
                    self.log_file = f"rag_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
                    self.key = os.path.join(prefix, self.log_file)
                    self.buffer = []
                    self.flush_interval = 10  # Flush every 10 messages; adjust as needed
                
                def emit(self, record):
                    msg = self.format(record)
                    self.buffer.append(msg + '\n')
                    if len(self.buffer) >= self.flush_interval:
                        self.flush()
                
                def flush(self):
                    if self.buffer:
                        body = ''.join(self.buffer)
                        try:
                            self.s3.put_object(Bucket=self.bucket, Key=self.key, Body=body)
                            self.buffer = []  # Clear after successful upload
                        except ClientError as e:
                            # Handle upload error (e.g., log to console)
                            print(f"S3 log upload failed: {e}")
                
                def close(self):
                    self.flush()
                    super().close()
            
            s3_handler = S3Handler(s3_bucket, s3_prefix)
            s3_handler.setLevel(logging.INFO)
            s3_handler.setFormatter(formatter)
            logger.addHandler(s3_handler)
    
    return logger

# Create default logger instance (pass your bucket name; e.g., from env var)
logger = setup_logger(s3_bucket=load_config("AWS_S3_BUCKET"))  # Adjust bucket env var as needed