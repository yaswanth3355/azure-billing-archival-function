import azure.functions as func
import os
import json
import gzip
from azure.cosmos import CosmosClient
from azure.storage.blob import BlobServiceClient
import logging

def main(req: func.HttpRequest) -> func.HttpResponse:
    cosmos_client = CosmosClient(os.environ["COSMOS_ENDPOINT"], os.environ["COSMOS_KEY"])
    database = cosmos_client.get_database_client("BillingDB")
    container = database.get_container_client("BillingRecords")
    
    blob_service_client = BlobServiceClient.from_connection_string(os.environ["BLOB_CONNECTION_STRING"])
    blob_container_client = blob_service_client.get_container_client("billing-records")

    if req.method == "POST":
        # Handle write request
        try:
            record = req.get_json()
            container.create_item(record)
            return func.HttpResponse(json.dumps({"message": "Record created"}), status_code=201, mimetype="application/json")
        except Exception as e:
            logging.error(f"Write failed: {str(e)}")
            return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500, mimetype="application/json")

    elif req.method == "GET":
        # Handle read request
        record_id = req.params.get("recordId")
        if not record_id:
            return func.HttpResponse(json.dumps({"error": "recordId is required"}), status_code=400, mimetype="application/json")
        
        try:
            # Try Cosmos DB first
            item = container.read_item(item=record_id, partition_key=record_id)
            return func.HttpResponse(json.dumps(item), status_code=200, mimetype="application/json")
        except:
            # Try Blob Storage
            blob_name = f"billing_records/{record_id}.json"
            blob_client = blob_container_client.get_blob_client(blob_name)
            try:
                blob_data = blob_client.download_blob().readall()
                decompressed_data = gzip.decompress(blob_data)
                record = json.loads(decompressed_data.decode('utf-8'))
                return func.HttpResponse(json.dumps(record), status_code=200, mimetype="application/json")
            except Exception as e:
                logging.error(f"Read from Blob Storage failed: {str(e)}")
                return func.HttpResponse(json.dumps({"error": "Record not found"}), status_code=404, mimetype="application/json")
