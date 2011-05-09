import uuid

from zope.container.interfaces import IOrderedContainer
from zope.interface import Interface
from zope.location.interfaces import ILocation

from zope import schema


class IRecord(ILocation):
    """
    A record is an object with a unique id (RFC 4122 UUID) stored in 
    string form as an attribute or property of the object, with a location
    context (ILocation __parent__ and __name__) attributes.
    """
    record_uid = schema.BytesLine(
        title=u'Record UID',
        description=u'Record UUID in string format',
        defaultFactory=lambda: str(uuid.uuid4()), #random UUID
        )


class IRecordContainer(IOrderedContainer):
    """
    An ordered readable container of records with an additional set of 
    CRUD convenience methods for managing contained records.  Keys are
    string representations of UUIDs, and values are objects providing 
    IRecord.
    """
    
    factory = schema.Object(
        title=u'Record factory/class',
        schema=IRecord,
        required=True,
        )
    
    def create(data):
        """
        Alternative factory for an IRecord object, does not store object.
        If data is not None, copy fields from data.
        """
    
    def add(record):
        """
        Add a record to container, append UUID to end of order; over-
        write existing entry if already exists for a UUID (in such case
        leave order as-is).
        """
    
    def reorder(record, offset):
        """
        Reorder a record (either UUID or object with record_uid attribute)
        in self.order, if record exists.  If no UUID exists in self.order, 
        raise a ValueError.  Offset must be non-negative integer. 
        """
    
    def updateOrder(order):
        """Key-based reorder, see zope.container.interfaces.IOrdered"""
    
    def update(data):
        """
        Given data, which may be a dict of field key/values or an actual 
        IRecord providing object, update existing entry given a UUID, or 
        add the entry if an entry for that UUID does not yet exist.  The
        update should copy all values for every key provided.  Specialized
        or schema-bound subclasses of this interface may execute more 
        elaborate rules on what data is copied and how it is normalized.
        
        Pre-condition:
        
          * All new (added) entries updated this way must contain a record_uid
            field with a string UUID.
        
        Post-condition:
        
          * New items should always be handled through self.create() and then
            self.add().
        
          * Method returns modified record.
        
          * Should notify at least zope.lifecycleevent.IObjectModifiedEvent,
            (if changes, detection of which is left up to implementation).
        
          * On creation of new records, should notify both
            IObjectCreatedEvent and IObjectAddedEvent (the record container
            is the context of record).
        
        """
    
    def update_all(data):
        """
        Given sequence of data dictionaries or a JSON serialization
        thereof, update each item.  Raises ValueError on missing UID of
        any item/entry.  Also supports JSON serialization of a single
        record/entry dict.
        """
    
    def get(uid, default=None):
        """
        Get object providing IRecord for given UUID uid or return None
        """
    
    def __contains__(record):
        """
        Given record as either IRecord object or UUID, is record
        contained in self.entries?
        """
    
    def __len__():
        """ return length of record entries """
    
    def __getitem__(key):
        """Get item by UID key"""
    
    def keys():
        """return tuple with elements identical to self.order"""
    
    def values():
        """return tuple of Chart Entries in order"""
    
    def items():
        """return ordered pairs of key/values"""
    
    def __iter__():
        """Return iterator for the keys (uuids) / self.order"""
    
    def __delitem__(name):
        """
        remove item given a name, or given a record object in place of
        name as the first positional argument.  Raises KeyError on item
        not found.
        """
    
    def __setitem__(name, value):
        """
        Set item into container, name must be uuid, value must be IRecord
        object.
        """


class IRecordResolver(Interface):
    """
    Utility interface for fetching records by UUID.
    
    Trivial usage example
    ---------------------
    
    Some imports:
    
    >>> import uuid
    >>> from zope.component import queryUtility, getGlobalSiteManager
    >>> from zope.interface import implements
    >>> from uu.record.interfaces import IRecordResolver
    
    Dummy record object with some arbitrary implementation-specific
    attribute to store the UID:
    
    >>> class Dummy(object):
    ...     uid = str(uuid.uuid4())
    ... 
    >>> dummy = Dummy()
    
    We don't have a resolver utility yet:
    
    >>> assert queryUtility(IRecordResolver) is None
    
    Create and register a trivial example resolver:
    
    >>> class DummyResolver(object):
    ...     implements(IRecordResolver)
    ...     def __call__(self, uid):
    ...         uid = str(uid)
    ...         if uid == dummy.uid:
    ...             return dummy #not very useful, but demonstrative.
    ...         return None
    ...     def context(self, uid):
    ...         return getattr(self(uid), '__parent__', None)
    ...     def contained(self, uid):
    ...         return (self.context(uid), self(uid)) #works, unoptimized
    ... 
    >>> gsm = getGlobalSiteManager()
    >>> gsm.registerUtility(DummyResolver())
    
    Get and query the resolver:
    >>> resolve = queryUtility(IRecordResolver)
    >>> obj = resolve(uid)
    >>> assert obj is dummy
    
    Work with context:
    >>> container = resolve.context(uid)
    >>> assert container is None  #dummy obj never had context
    
    Let's create a parent object for context for the dummy implementation:
    
    >>> parent = Dummy()
    >>> dummy.__parent__ = parent
    >>> assert resolve.context(uid) is parent #well, it is now.
    
    There is also a contained() method returning both context and object as
    a tuple that can be unpacked in simple calling:
    
    >>> container, obj = resolve.contained(uid)
    >>> assert obj is dummy
    >>> assert container is parent
    
    Clean-up: remove the DummyResolver utility from the site manager:
    
    >>> gsm.unregisterUtility(DummyResolver)
    
    """
    
    def __call__(uid):
        """
        Given uid as uuid.UUID object or as string representation of UUID, 
        return a record object.
        """
    
    def context(uid):
        """
        Return None or an object represnting a context of or container for
        the record that would be retrieved by __call__().  This may be, 
        for records providing zope.location.interfaces.ILocation, a parent 
        container obtained by following a reference to obj.__parent__ or
        it may come from some other context, such as an adaptation context.
        """
    
    def contained(uid):
        """
        Return tuple of context, object.  Implementations should ideally
        avoid lookup/retrieval of object more than once.
        """

