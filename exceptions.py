class Error(Exception):
    """Base class for other exceptions"""
    pass


class ProductNotFoundException(Error):
    """Raised when page was not found"""
    pass


class ProductOverviewException(Error):
    pass


class LoadingProductException(Error):
    pass


class OutOfBoundException(Error):
    """
    Raised when trying to scrap from non-existent link
    """
    pass

class NoProductsOverview(Error):
    pass


class UniqueIdException(Error):
    pass