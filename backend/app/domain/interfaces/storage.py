"""Domain abstraction for Object Storage providers (S3, MinIO, Azure Blob, GCS)."""

from abc import ABC, abstractmethod


class ObjectStorageInterface(ABC):
    """Abstract interface to decouple raw document/blob storage."""

    @abstractmethod
    async def upload_file(
        self,
        bucket_name: str,
        object_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Uploads file content and returns the canonical URI or path."""
        pass

    @abstractmethod
    async def download_file(self, bucket_name: str, object_key: str) -> bytes:
        """Downloads complete file content."""
        pass

    @abstractmethod
    async def delete_file(self, bucket_name: str, object_key: str) -> bool:
        """Deletes file from storage."""
        pass

    @abstractmethod
    async def file_exists(self, bucket_name: str, object_key: str) -> bool:
        """Checks if a file exists in storage."""
        pass

    @abstractmethod
    async def generate_presigned_url(
        self,
        bucket_name: str,
        object_key: str,
        expires_seconds: int = 3600,
    ) -> str | None:
        """Generates a temporary pre-signed download URL."""
        pass

    async def save(self, data: bytes, key: str, content_type: str = "application/octet-stream") -> str:
        """Convenience method saving object under default documents bucket."""
        return await self.upload_file("documents", key, data, content_type)

    async def load(self, key: str) -> bytes:
        """Convenience method loading object from default documents bucket."""
        return await self.download_file("documents", key)

    async def delete(self, key: str) -> bool:
        """Convenience method deleting object from default documents bucket."""
        return await self.delete_file("documents", key)

    async def exists(self, key: str) -> bool:
        """Convenience method checking object presence in default documents bucket."""
        return await self.file_exists("documents", key)

