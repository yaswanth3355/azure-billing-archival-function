import azure.functions as func
import os
import json
import gzip
from datetime import datetime, timedelta
from azure.cosmos import CosmosClient
from azure.storage.blob import BlobServiceClient
import logging

def main(mytimer: func.TimerRequest) -> None:
    # Initialize clients
    cosmos_client = CosmosClient(os.environ["COSMOS_ENDPOINT"], os.environ["COSMOS_KEY"])
    database = cosmos_client.get_database_client("BillingDB")
    container = database.get_container_client("BillingRecords")
    
    blob_service_client = BlobServiceClient.from_connection_string(os.environ["BLOB_CONNECTION_STRING"])
    blob_container_client = blob_service_client.get_container_client("billing-records")

    # Query records older than 85 days
    threshold = (datetime.utcnow() - timedelta(days=85)).isoformat()
    query = f"SELECT * FROM c WHERE c.createdDate < '{threshold}'"
    items = container.query_items(query=query, enable_cross_partition_query=True)

    for item in items:
        try:
            # Compress record
            record_data = json.dumps(item).encode('utf-8')
            compressed_data = gzip.compress(record_data)
            blob_name = f"billing_records/{item['recordId']}.json"
            blob_client = blob_container_client.get_blob_client(blob_name)

            # Upload to Blob Storage
            blob_client.upload_blob(compressed_data, overwrite=True)
            logging.info(f"Archived record {item['recordId']} to Blob Storage")
        except Exception as e:
            logging.error(f"Failed to archive record {item['recordId']}: {str(e)}")
