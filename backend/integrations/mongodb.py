"""
MongoDB Integration - FULLY IMPLEMENTED

Real MongoDB Data API integration for document database operations.

Supported Actions:
- find_one: Find a single document
- find: Find multiple documents
- insert_one: Insert a single document
- insert_many: Insert multiple documents
- update_one: Update a single document
- update_many: Update multiple documents
- delete_one: Delete a single document
- delete_many: Delete multiple documents
- aggregate: Run aggregation pipeline
- count: Count documents

Authentication: API Key (MongoDB Data API) or Connection String
API Docs: https://www.mongodb.com/docs/atlas/api/data-api/
"""

import aiohttp
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType


class MongoDBIntegration(BaseIntegration):
    """MongoDB integration with Data API."""

    @property
    def name(self) -> str:
        return "mongodb"

    @property
    def display_name(self) -> str:
        return "MongoDB"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.API_KEY

    @property
    def supported_actions(self) -> List[str]:
        return [
            "find_one",
            "find",
            "insert_one",
            "insert_many",
            "update_one",
            "update_many",
            "delete_one",
            "delete_many",
            "aggregate",
            "count",
        ]

    def _validate_credentials(self) -> None:
        """Validate MongoDB credentials."""
        super()._validate_credentials()

        # Data API requires api_key and data_source
        if "api_key" not in self.auth_credentials:
            raise IntegrationError(
                "MongoDB requires 'api_key' for Data API",
                code="MISSING_CREDENTIALS",
            )

        if "data_source" not in self.auth_credentials and "cluster" not in self.auth_credentials:
            raise IntegrationError(
                "MongoDB requires 'data_source' or 'cluster' name",
                code="MISSING_CREDENTIALS",
            )

        if "app_id" not in self.auth_credentials and "endpoint" not in self.auth_credentials:
            raise IntegrationError(
                "MongoDB requires 'app_id' or 'endpoint' URL",
                code="MISSING_CREDENTIALS",
            )

    def _get_endpoint_url(self) -> str:
        """Get MongoDB Data API endpoint URL."""
        if "endpoint" in self.auth_credentials:
            return self.auth_credentials["endpoint"]

        app_id = self.auth_credentials["app_id"]
        region = self.auth_credentials.get("region", "us-east-1")
        return f"https://{region}.aws.data.mongodb-api.com/app/{app_id}/endpoint/data/v1"

    def _get_data_source(self) -> str:
        """Get data source (cluster) name."""
        return self.auth_credentials.get("data_source") or self.auth_credentials.get("cluster")

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers with auth."""
        return {
            "api-key": self.auth_credentials["api_key"],
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _make_request(
        self,
        action: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Make HTTP request to MongoDB Data API.

        Args:
            action: API action (findOne, find, insertOne, etc.)
            data: Request payload

        Returns:
            API response as dict

        Raises:
            IntegrationError: If API call fails
        """
        url = f"{self._get_endpoint_url()}/action/{action}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=self._get_headers(),
                    json=data,
                ) as response:
                    response_data = await response.json()

                    if response.status >= 400:
                        error_msg = response_data.get("error", str(response_data))
                        raise IntegrationError(
                            f"MongoDB API error: {error_msg}",
                            code="MONGODB_ERROR",
                            status_code=response.status,
                            details=response_data,
                        )

                    return response_data

        except aiohttp.ClientError as e:
            raise IntegrationError(
                f"HTTP request failed: {str(e)}",
                code="HTTP_ERROR",
            )
        except Exception as e:
            if isinstance(e, IntegrationError):
                raise
            raise IntegrationError(
                f"Unexpected error: {str(e)}",
                code="UNKNOWN_ERROR",
            )

    async def execute_action(
        self,
        action: str,
        params: Dict[str, Any],
    ) -> IntegrationResult:
        """Execute MongoDB action with real API call."""
        self._validate_action(action)
        start_time = datetime.utcnow()

        try:
            if action == "find_one":
                result = await self._find_one(params)
            elif action == "find":
                result = await self._find(params)
            elif action == "insert_one":
                result = await self._insert_one(params)
            elif action == "insert_many":
                result = await self._insert_many(params)
            elif action == "update_one":
                result = await self._update_one(params)
            elif action == "update_many":
                result = await self._update_many(params)
            elif action == "delete_one":
                result = await self._delete_one(params)
            elif action == "delete_many":
                result = await self._delete_many(params)
            elif action == "aggregate":
                result = await self._aggregate(params)
            elif action == "count":
                result = await self._count(params)
            else:
                raise IntegrationError(f"Action {action} not implemented", code="NOT_IMPLEMENTED")

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            result.duration_ms = duration_ms

            self._log_execution(action, params, result)
            return result

        except IntegrationError as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            result = IntegrationResult(
                success=False,
                error_message=e.message,
                error_code=e.code,
                duration_ms=duration_ms,
            )
            self._log_execution(action, params, result)
            return result

    async def test_connection(self) -> IntegrationResult:
        """Test MongoDB connection by finding one document."""
        try:
            # Try to find any document in a test collection
            database = self.auth_credentials.get("database", "test")
            result = await self._find_one({
                "database": database,
                "collection": "test",
                "filter": {},
            })
            return IntegrationResult(
                success=True,
                data={
                    "connected": True,
                    "data_source": self._get_data_source(),
                },
            )
        except IntegrationError as e:
            # Connection test may fail if collection doesn't exist, but that's ok
            if "not found" in str(e.message).lower():
                return IntegrationResult(
                    success=True,
                    data={
                        "connected": True,
                        "data_source": self._get_data_source(),
                    },
                )
            return IntegrationResult(
                success=False,
                error_message=e.message,
                error_code=e.code,
            )

    # ========================================================================
    # Action Implementations
    # ========================================================================

    def _build_base_payload(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build base payload with dataSource, database, collection."""
        database = params.get("database")
        collection = params.get("collection")

        if not database or not collection:
            raise IntegrationError(
                "Missing required parameters: 'database' and 'collection'",
                code="MISSING_PARAMS",
            )

        return {
            "dataSource": self._get_data_source(),
            "database": database,
            "collection": collection,
        }

    async def _find_one(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Find a single document.

        Required params:
            database: Database name
            collection: Collection name

        Optional params:
            filter: Query filter
            projection: Fields to return
        """
        payload = self._build_base_payload(params)
        payload["filter"] = params.get("filter", {})

        if "projection" in params:
            payload["projection"] = params["projection"]

        response = await self._make_request("findOne", payload)

        return IntegrationResult(
            success=True,
            data={
                "document": response.get("document"),
            },
        )

    async def _find(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Find multiple documents.

        Required params:
            database: Database name
            collection: Collection name

        Optional params:
            filter: Query filter
            projection: Fields to return
            sort: Sort specification
            limit: Maximum documents to return
            skip: Documents to skip
        """
        payload = self._build_base_payload(params)
        payload["filter"] = params.get("filter", {})

        if "projection" in params:
            payload["projection"] = params["projection"]
        if "sort" in params:
            payload["sort"] = params["sort"]
        if "limit" in params:
            payload["limit"] = params["limit"]
        if "skip" in params:
            payload["skip"] = params["skip"]

        response = await self._make_request("find", payload)

        documents = response.get("documents", [])

        return IntegrationResult(
            success=True,
            data={
                "documents": documents,
                "count": len(documents),
            },
        )

    async def _insert_one(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Insert a single document.

        Required params:
            database: Database name
            collection: Collection name
            document: Document to insert
        """
        payload = self._build_base_payload(params)

        document = params.get("document")
        if not document:
            raise IntegrationError("Missing required parameter: 'document'", code="MISSING_PARAMS")

        payload["document"] = document

        response = await self._make_request("insertOne", payload)

        return IntegrationResult(
            success=True,
            data={
                "inserted_id": response.get("insertedId"),
            },
        )

    async def _insert_many(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Insert multiple documents.

        Required params:
            database: Database name
            collection: Collection name
            documents: List of documents to insert
        """
        payload = self._build_base_payload(params)

        documents = params.get("documents")
        if not documents:
            raise IntegrationError("Missing required parameter: 'documents'", code="MISSING_PARAMS")

        payload["documents"] = documents

        response = await self._make_request("insertMany", payload)

        return IntegrationResult(
            success=True,
            data={
                "inserted_ids": response.get("insertedIds", []),
                "count": len(response.get("insertedIds", [])),
            },
        )

    async def _update_one(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Update a single document.

        Required params:
            database: Database name
            collection: Collection name
            filter: Query filter
            update: Update operations

        Optional params:
            upsert: Insert if not found (default: False)
        """
        payload = self._build_base_payload(params)

        filter_doc = params.get("filter")
        update_doc = params.get("update")

        if filter_doc is None or update_doc is None:
            raise IntegrationError(
                "Missing required parameters: 'filter' and 'update'",
                code="MISSING_PARAMS",
            )

        payload["filter"] = filter_doc
        payload["update"] = update_doc

        if "upsert" in params:
            payload["upsert"] = params["upsert"]

        response = await self._make_request("updateOne", payload)

        return IntegrationResult(
            success=True,
            data={
                "matched_count": response.get("matchedCount", 0),
                "modified_count": response.get("modifiedCount", 0),
                "upserted_id": response.get("upsertedId"),
            },
        )

    async def _update_many(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Update multiple documents.

        Required params:
            database: Database name
            collection: Collection name
            filter: Query filter
            update: Update operations

        Optional params:
            upsert: Insert if not found (default: False)
        """
        payload = self._build_base_payload(params)

        filter_doc = params.get("filter")
        update_doc = params.get("update")

        if filter_doc is None or update_doc is None:
            raise IntegrationError(
                "Missing required parameters: 'filter' and 'update'",
                code="MISSING_PARAMS",
            )

        payload["filter"] = filter_doc
        payload["update"] = update_doc

        if "upsert" in params:
            payload["upsert"] = params["upsert"]

        response = await self._make_request("updateMany", payload)

        return IntegrationResult(
            success=True,
            data={
                "matched_count": response.get("matchedCount", 0),
                "modified_count": response.get("modifiedCount", 0),
                "upserted_id": response.get("upsertedId"),
            },
        )

    async def _delete_one(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Delete a single document.

        Required params:
            database: Database name
            collection: Collection name
            filter: Query filter
        """
        payload = self._build_base_payload(params)

        filter_doc = params.get("filter")
        if filter_doc is None:
            raise IntegrationError("Missing required parameter: 'filter'", code="MISSING_PARAMS")

        payload["filter"] = filter_doc

        response = await self._make_request("deleteOne", payload)

        return IntegrationResult(
            success=True,
            data={
                "deleted_count": response.get("deletedCount", 0),
            },
        )

    async def _delete_many(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Delete multiple documents.

        Required params:
            database: Database name
            collection: Collection name
            filter: Query filter
        """
        payload = self._build_base_payload(params)

        filter_doc = params.get("filter")
        if filter_doc is None:
            raise IntegrationError("Missing required parameter: 'filter'", code="MISSING_PARAMS")

        payload["filter"] = filter_doc

        response = await self._make_request("deleteMany", payload)

        return IntegrationResult(
            success=True,
            data={
                "deleted_count": response.get("deletedCount", 0),
            },
        )

    async def _aggregate(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Run aggregation pipeline.

        Required params:
            database: Database name
            collection: Collection name
            pipeline: Aggregation pipeline stages
        """
        payload = self._build_base_payload(params)

        pipeline = params.get("pipeline")
        if not pipeline:
            raise IntegrationError("Missing required parameter: 'pipeline'", code="MISSING_PARAMS")

        payload["pipeline"] = pipeline

        response = await self._make_request("aggregate", payload)

        documents = response.get("documents", [])

        return IntegrationResult(
            success=True,
            data={
                "documents": documents,
                "count": len(documents),
            },
        )

    async def _count(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Count documents.

        Required params:
            database: Database name
            collection: Collection name

        Optional params:
            filter: Query filter
        """
        # Use aggregation with $count for count operation
        payload = self._build_base_payload(params)

        pipeline = []
        if "filter" in params and params["filter"]:
            pipeline.append({"$match": params["filter"]})
        pipeline.append({"$count": "count"})

        payload["pipeline"] = pipeline

        response = await self._make_request("aggregate", payload)

        documents = response.get("documents", [])
        count = documents[0]["count"] if documents else 0

        return IntegrationResult(
            success=True,
            data={
                "count": count,
            },
        )
