from abc import ABC, abstractmethod


# the db instance
# one db instance may contain multiple collections, have a default collection here
class DBInstance(ABC):
    def __init__(self, **kwargs):
        self.db_path = kwargs.get("db_path", None)
        self.collections = kwargs.get("collections", [])
        self.default_collection = kwargs.get("collection_name", None)
        # self.device = kwargs.get("device", "cpu")
        self.drop_previous_collection = kwargs.get("drop_previous_collection", False)
        self.client = None

    @abstractmethod
    def setup(self):
        pass

    # collection related
    @abstractmethod
    def create_collection(self, collection_name):
        # Create a new collection in the database.
        pass

    @abstractmethod
    def has_collection(self, collection_name):
        """
        Check if the collection exists in the database.
        :param collection_name: Name of the collection to check.
        :return: True if the collection exists, False otherwise.
        """
        pass

    @abstractmethod
    def drop_collection(self, collection_name):
        """
        Drop the specified collection from the database.
        :param collection_name: Name of the collection to drop.
        """
        pass

    @abstractmethod
    def insert_data(self, vectors, chunks, collection_name=None):
        """
        Insert data into the database.
        :param vectors: Embeddings to be inserted.
        :param chunks: Corresponding text chunks.
        """
        pass

    @abstractmethod
    def query_search(self, query_vector, collection_name=None):
        pass

    # @abstractmethod
    # def close(self):
    #     """
    #     Close the database connection.
    #     """
    #     pass
