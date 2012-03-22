import json
import decimal
import time
import uuid
from datetime import date, datetime, timedelta

from persistent import Persistent
from persistent.dict import PersistentDict
from persistent.list import PersistentList
from zope.event import notify
from zope.lifecycleevent import ObjectCreatedEvent, ObjectModifiedEvent
from zope.lifecycleevent import ObjectAddedEvent, ObjectRemovedEvent
from zope.lifecycleevent import Attributes
from zope.interface import implements
from BTrees.OOBTree import OOBTree

from uu.record.interfaces import IRecord, IRecordContainer


class Record(Persistent):
    implements(IRecord)
    
    record_uid = None
    
    def __init__(self, context=None, uid=None):
        self.context = self.__parent__ = context
        if uid is None:
            uid = str(uuid.uuid4())
        self.record_uid = str(uid)
    
    @property
    def __name__(self):
        return self.record_uid


class RecordContainer(Persistent):
    """
    Base/default record container uses PersistentDict for entry storage
    and PersistentList to store ordered keys.  This base container class
    does not advocate one place of storage for the container in a ZODB
    over another, so subclass implementations may choose to implement a 
    container within a placeful (e.g. OFS or CMF Content item) or placeless
    (local utility) storage context.  Only a placeless context is supported
    by direct users of this class (without subclassing).
    
    For a container with hundreds of items or more, consider using instead
    BTreeRecordContainer as an implementation or base class, as it should 
    handle memory usage and insert performance much better for larger sets
    of records.
    
    Usage
    -----
    
    RecordContainer acts as CRUD controller for working with records.
    
    The RecordContainer is an addressible object in the system, either as a 
    registered utility (or with a subclass as "contentish" (CMF) content).
    
    Records themselves are not content, but data that are possibly 
    non-atomic elements of an atomic content item (if the container is 
    implemented in a subclass of RecordContainer as contentish).
    
    Usage:
    ------
    
    We need a record container object:
    
    >>> from uu.record.base import Record, RecordContainer
    >>> container = RecordContainer()
    >>> from uu.record.interfaces import IRecordContainer
    >>> assert IRecordContainer.providedBy(container)
    
    Record containers have length and containment checks:
    
    >>> assert len(container) == 0
    >>> import uuid #keys for entries are stringified UUIDs
    >>> randomuid = str(uuid.uuid4())
    >>> assert randomuid not in container
    >>> assert container.get(randomuid, None) is None
    
    And they have keys/values/items methods like a mapping:
    
    >>> assert container.keys() == ()
    >>> assert container.values() == ()
    >>> assert container.items() == () #of course, these are empty now.

    Before we add records to a container, we need to create them; there are
    two possible ways to do this:

    >>> from uu.record.base import Record
    >>> entry1 = Record()
    >>> entry2 = container.create() #preferred factory

    Both factory mechanisms create an entry item with a record_uid attribute:

    >>> from uu.record.interfaces import IRecord
    >>> assert IRecord.providedBy(entry1)
    >>> assert IRecord.providedBy(entry2)
    >>> is_uuid = lambda u: isinstance(u, str) and len(u)==36
    >>> assert is_uuid(entry1.record_uid)
    >>> assert is_uuid(entry2.record_uid)

    And, these are RFC 4122 UUIDs, so even randomly generated 128-bit ids
    have near zero chance of collision:
    
    >>> assert entry1.record_uid != entry2.record_uid
    >>> assert entry2.record_uid != randomuid
        
    Now when we have a parent context with a schema, the created entries will
    be signed with the schema and provide it.
    
    RecordContainer.create() is the preferred factory when processing data.
    This is because it can take a mapping of keys/values, and copy each
    field name/value onto object attributes -- if and only if the attribute
    in question matches a type whitelist and a name blacklist filter.
    
    >>> entry4 = container.create(data={'record_uid':randomuid})
    >>> assert entry4.record_uid == randomuid
    >>> entry5 = container.create(data={'count':5})
    >>> assert entry5.count == 5
    >>> entry6 = container.create(data={'_bad_name'    : True,
    ...                                  'count'        : 2,
    ...                                  'bad_value'    : lambda x: x })
    >>> assert not hasattr(entry6, '_bad_name') #no leading underscores
    >>> assert entry6.count == 2
    >>> assert not hasattr(entry6, 'bad_value') #function not copied!

    Of course, merely using the record container object as a factory for
    new records does not mean they are stored within (yet):

    >>> assert entry4.record_uid not in container
    >>> assert entry4.record_uid not in container.keys()
    
    Let's add an item:

    >>> container.add(entry4)
    
    There are two ways to check for containment, by either key or value:
    
    >>> assert entry4 in container
    >>> assert entry4.record_uid in container
    
    We can get records using a (limited, read) mapping-like interface:

    >>> assert len(container) == 1 # we just added the first entry
    >>> assert container.values()[0] is entry4
    >>> assert container.get(entry4.record_uid) is entry4
    >>> assert container[entry4.record_uid] is entry4

    We can deal with references to entries also NOT in the container:
    
    >>> import uuid
    >>> randomuid = str(uuid.uuid4())
    >>> assert randomuid not in container
    >>> assert container.get(str(uuid.uuid4()), None) is None
    >>> assert entry1.record_uid not in container
    
    And we can check containment on either an instance or a UID; checking on
    an instance is just a convenience that uses its UID (record_uid) field
    to check for actual containment:
    
    >>> assert entry4.record_uid in container
    >>> assert entry4 in container #shortcut!
    
    However, it should be noted for good measure:
    
    >>> assert entry4 in container.values()
    >>> assert entry4.record_uid in container.keys()
    >>> assert entry4 not in container.keys() # of course!
    >>> assert (entry4.record_uid, entry4) in container.items()
    
    We can modify a record contained directly; this is the most direct and 
    low-level update interface for any entry:
    
    >>> _marker = object()
    >>> assert getattr(entry4, 'title', _marker) is _marker
    >>> entry4.title = u'Curious George'
    >>> assert container.get(entry4.record_uid).title == u'Curious George'
    
    We can add another record:
    
    >>> container.add(entry6)
    >>> assert entry6 in container
    >>> assert entry6.record_uid in container
    >>> assert len(container) == 2
    
    Keys, values, items are always ordered; since we added entry4, then
    entry6 previously, they will return in that order:

    >>> expected_order = (entry4, entry6)
    >>> expected_uid_order = tuple([e.record_uid for e in expected_order])
    >>> expected_items_order = tuple(zip(expected_uid_order, expected_order))
    >>> assert tuple(container.keys()) == expected_uid_order
    >>> assert tuple(container.values()) == expected_order
    >>> assert tuple(container.items()) == expected_items_order
    
    We can re-order this; let's move entry6 up to position 0 (first):
    
    >>> container.reorder(entry6, offset=0)
    >>> expected_order = (entry6, entry4)
    >>> expected_uid_order = tuple([e.record_uid for e in expected_order])
    >>> expected_items_order = tuple(zip(expected_uid_order, expected_order))
    >>> assert tuple(container.keys()) == expected_uid_order
    >>> assert tuple(container.values()) == expected_order
    >>> assert tuple(container.items()) == expected_items_order
    
    We can also re-order by UID instead of record/entry reference:
    
    >>> container.reorder(entry6.record_uid, offset=1) #where it was before
    >>> expected_order = (entry4, entry6)
    >>> expected_uid_order = tuple([e.record_uid for e in expected_order])
    >>> expected_items_order = tuple(zip(expected_uid_order, expected_order))
    >>> assert tuple(container.keys()) == expected_uid_order
    >>> assert tuple(container.values()) == expected_order
    >>> assert tuple(container.items()) == expected_items_order
    
    And we can remove records from containment by UID or by reference (note,
    del(container[key]) uses __delitem__ since a container is a writable
    mapping):
    
    >>> del(container[entry6])
    >>> assert entry6 not in container
    >>> assert entry6.record_uid not in container
    >>> assert len(container) == 1
    >>> assert entry4 in container
    >>> del(container[entry4.record_uid])
    >>> assert entry4 not in container
    >>> assert len(container) == 0
    
    Earlier, direct update of objects was demonstrated: get an object and
    modify its properties.  This attribute-setting mechanism is the best
    low-level interface, but it does not (a) support a wholesale update
    from either a field dictionary/mapping nor another object providing
    IRecord needing its data to be copied; nor (b) support notification
    of zope.lifecycle object events.
    
    Given these needs, a high level interface for update exists, with the 
    record object acting as a controller for updating contained entries.
    This provides for update via another entry (a field-by-field copy) or 
    from a data dictionary/mapping.
    
    >>> newuid = str(uuid.uuid4())
    >>> data = {    'record_uid' : newuid, 
    ...             'title'      : u'George',
    ...             'count'      : 9,
    ...        }
    >>> assert len(container) == 0 #empty, nothing in there yet!
    >>> assert newuid not in container
    
    Note, update() returns an entry; return value can be ignored if caller
    deems it not useful.
    
    >>> entry = container.update(data)
    >>> assert newuid in container #update implies adding!
    >>> assert entry is container.get(newuid)
    >>> assert entry.title == data['title']
    >>> assert entry.count == data['count']
    
    Now, the entry we just modified was also added.  We can modify it again:
    
    >>> data = {    'record_uid' : newuid, 
    ...             'title'      : u'Curious George',
    ...             'count'      : 2,
    ...        }
    >>> entry = container.update(data)
    >>> assert newuid in container     # same uid
    >>> entry.title
    u'Curious George'
    >>> entry.count
    2
    >>> assert len(container) == 1     # same length, nothing new was added.
    
    We could also create a stand-in entry for which data is copied to the
    permanent entry with the same UUID on update:
    
    >>> temp_entry = container.create()
    >>> temp_entry.record_uid = newuid      # overwrite with the uid of entry
    >>> temp_entry.title = u'Monkey jumping on the bed'
    >>> temp_entry.count = 0
    
    temp_entry is a stand-in which we will pass to update(), when we really
    intend to modify entry (they have the same UID):
    
    >>> real_entry = container.update(temp_entry)
    >>> assert container.get(newuid) is not temp_entry
    >>> assert container.get(newuid) is entry  # still the same object...
    >>> assert container.get(newuid) is real_entry
    >>> entry.title                             # ...but data is modified!
    u'Monkey jumping on the bed'
    >>> entry.count
    0
    >>> assert len(container) == 1     # same length, nothing new was added.
    
    
    JSON integration
    ----------------
    
    As a convenience, update_all() parses JSON into a data dict for use by
    update(), using the Python 2.6 json library (aka/was: simplejson):
    
    >>> party_form = RecordContainer()
    >>> entry = party_form.create()
    >>> party_form.add(entry)
    >>> data = { #mock data we'll serialize to JSON
    ...     'record_uid': entry.record_uid, #which record to update
    ...     'name'      : 'Me',
    ...     'birthday'  : u'77/06/01',
    ...     'party_time': u'11/06/05 12:00',
    ...     }
    >>> import json #requires Python >= 2.6
    >>> data['name'] = 'Chunky monkey'
    >>> serialized = json.dumps([data,], indent=2) #JSON array of one item...
    >>> print serialized #doctest: +ELLIPSIS
    [
      {
        "party_time": "11/06/05 12:00", 
        "birthday": "77/06/01", 
        "name": "Chunky monkey", 
        "record_uid": "..."
      }
    ]
    
    The JSON created above is useful enough for demonstration, despite being
    only a single-item list.
    
    >>> assert getattr(entry, 'name', _marker) is _marker #before, no attr
    >>> party_form.update_all(serialized)
    >>> entry.name #after update
    u'Chunky monkey'
    
    update_all() also takes a singular record, not just a JSON array:
    
    >>> data['name'] = 'Curious George'
    >>> serialized = json.dumps(data, indent=2) # JSON object, not array.
    >>> print serialized #doctest: +ELLIPSIS
    {
      "party_time": "11/06/05 12:00", 
      "birthday": "77/06/01", 
      "name": "Curious George", 
      "record_uid": "..."
    }
    >>> entry.name #before
    u'Chunky monkey'
    >>> party_form.update_all(serialized)
    >>> entry.name #after update
    u'Curious George'
    
    JSON parsing also supports a "bundle" or wrapper object around a list of 
    entries, where the wrapper contains metadata about the form itself, not
    its entries (currently, this is just the process_changes field, which
    is sourced from the JSON bundle/wrapper object field called 'notes').
    When wrapped, the list of entries is named 'entries' inside the wrapper.
    
    >>> data['name'] = u'Party monkey'
    >>> serialized = json.dumps({'notes'    : 'something changed',
    ...                          'entries'  : [data,]},
    ...                         indent=2) #JSON array of one item...
    >>> entry.name #before
    u'Curious George'
    >>> party_form.update_all(serialized)
    >>> entry.name #after
    u'Party monkey'
    
    It should be noted that update_all() removes entries not in the data 
    payload, and it preserves the order contained in the JSON entries.
    
    Object events
    -------------
    
    CRUD methods on a controlling object should have some means of extension,
    pluggable to code that should subscribe to CRUD (object lifecycle) events.
    We notify four distinct zope.lifecycleevent object event types:

    1. Object created (zope.lifecycleevent.interfaces.IObjectCreatedEvent)
    
    2. Object addded to container:
        (zope.lifecycleevent.interfaces.IObjectAddedEvent).
    
    3. Object modified (zope.lifecycleevent.interfaces.IObjectModifiedEvent)
    
    4. Object removed (zope.lifecycleevent.interfaces.IObjectRemovedEvent)
    
    Note: the create() operation both creates and modifies: as such, both
    created and modified events are fired off, and since most creations also
    are followed by an add() to a container, you may have three events to
    subscribe to early in a new entry's lifecycle.
    
    First, some necessary imports of events and the @adapter decorator:
    
    >>> from zope.component import adapter
    >>> from zope.lifecycleevent import IObjectCreatedEvent
    >>> from zope.lifecycleevent import IObjectModifiedEvent
    >>> from zope.lifecycleevent import IObjectRemovedEvent
    >>> from zope.lifecycleevent import IObjectAddedEvent
    
    Let's define dummy handlers:
    
    >>> @adapter(IRecord, IObjectCreatedEvent)
    ... def handle_create(context, event):
    ...     print 'object created'
    ... 
    >>> @adapter(IRecord, IObjectModifiedEvent)
    ... def handle_modify(context, event):
    ...     print 'object modified'
    ... 
    >>> @adapter(IRecord, IObjectRemovedEvent)
    ... def handle_remove(context, event):
    ...     print 'object removed'
    ... 
    >>> @adapter(IRecord, IObjectAddedEvent)
    ... def handle_add(context, event):
    ...     print 'object added'
    ... 
    
    Next, let's configure zope.event to use zope.component event subscribers;
    most frameworks using zope.lifecycleevent already do this, but we will
    configure this explicitly for documentation/testing purposes:
    
    >>> import zope.event
    >>> from zope.component.event import objectEventNotify
    >>> zope.event.subscribers.append(objectEventNotify)
    
    Now, let's register the handlers:
    
    >>> from zope.component import getGlobalSiteManager
    >>> gsm = getGlobalSiteManager()
    >>> for h in (handle_create, handle_modify, handle_remove, handle_add):
    ...     gsm.registerHandler(h)
    ... 
    
    Usually, these handlers will be registered in the global site manager
    via ZCML and zope.configuration, but they are registered in Python
    above for documentation/testing purposes.
    
    We can watch these event handlers get fired when CRUD methods are called.
    
    Object creation, with and without data:
    
    >>> newentry = container.create()      #should print 'object created'
    object created
    >>> another_uid = str(uuid.uuid4())
    >>> newentry = container.create({'count':88})
    object modified
    object created
    
    Object addition:
    
    >>> container.add(newentry)
    object added
    >>>
    
    Object removal:
    
    >>> del(container[newentry.record_uid]) # via __delitem__()
    object removed
    
    Object update (existing object):
    
    >>> entry = container.values()[0]
    >>> entry = container.update({'record_uid' : entry.record_uid,
    ...                            'title'      : u'Me'})
    object modified
    
    Object modified (new object or not contained): 
    
    >>> random_uid = str(uuid.uuid4())
    >>> entry = container.update({'record_uid' : random_uid,
    ...                            'title'      : u'Bananas'})
    object modified
    object created
    object added
    
    Event handlers for modification can know what fields are modified; let's
    create a more interesting modification handler that prints the names of
    changed fields.

    >>> from zope.lifecycleevent.interfaces import IAttributes
    >>> unregistered = gsm.unregisterHandler(handle_modify)
    >>> @adapter(IRecord, IObjectModifiedEvent)
    ... def handle_modify(context, event):
    ...     if event.descriptions:
    ...         attr_desc = [d for d in event.descriptions
    ...                         if (IAttributes.providedBy(d))]
    ...         if attr_desc:
    ...             field_names = attr_desc[0].attributes
    ...         print tuple(field_names)
    >>> gsm.registerHandler(handle_modify)
    
    >>> entry = container.values()[0]
    >>> entry = container.update({'record_uid' : entry.record_uid,
    ...                            'title'      : u'Hello'})
    ('title',)

    Finally, clean up and remove all the dummy handlers:
    >>> for h in (handle_create, handle_modify, handle_remove, handle_add):
    ...     success = gsm.unregisterHandler(h)
    ... 
    
    """
    
    implements(IRecordContainer)
    
    # whitelist types of objects to copy on data update:
    
    TYPE_WHITELIST = (int,
                      long,
                      str,
                      unicode,
                      bool,
                      float,
                      time.time,
                      datetime,
                      date,
                      timedelta,
                      decimal.Decimal,)
    
    SEQUENCE_WHITELIST = (list, tuple, set, frozenset, PersistentList,)
    
    MAPPING_WHITELIST = (dict, PersistentDict,)
    
    RECORD_INTERFACE = IRecord
    
    factory = Record
    
    def __init__(self, factory=Record, _impl=PersistentDict):
        self._entries = _impl()
        self._order = PersistentList()
        self.factory = factory
    
    # IWriteContainer methods:
    
    def __setitem__(self, key, value):
        if isinstance(key, uuid.UUID) or isinstance(key, unicode):
            key = str(key)
        elif not (isinstance(key, str) and len(key)==36):
            raise KeyError('key does not appear to be string UUID: %s', key)
        if not self.RECORD_INTERFACE.providedBy(value):
            raise ValueError('Record value must provide %s' % (
                self.RECORD_INTERFACE.__identifier__))
        self._entries[key] = value
        if key not in self._order:
            self._order.append(key)
    
    def __delitem__(self, record):
        uid = record
        if self.RECORD_INTERFACE.providedBy(record):
            uid = str(record.record_uid)
        elif isinstance(record, uuid.UUID):
            uid = str(record)
        if not (isinstance(uid, str) and len(uid)==36):
            raise ValueError('record neither record object nor UUID')
        if uid not in self._entries:
            raise ValueError('record not found contained within')
        if uid in self._order:
            self._order.remove(uid)
        if not self.RECORD_INTERFACE.providedBy(record):
            record = self._entries.get(uid) #need ref for event notify below
        del(self._entries[uid])
        notify(ObjectRemovedEvent(record, self, uid))
    
    # IRecordContainer and IOrdered re-ordering methods:
    
    def reorder(self, record, offset):
        """
        Reorder a record (either UUID or object with record_uid attribute)
        in self._order, if record exists.  If no UUID exists in self._order, 
        raise a ValueError.  Offset must be non-negative integer. 
        """
        uid = record
        offset = abs(int(offset))
        if self.RECORD_INTERFACE.providedBy(record):
            uid = record.record_uid
        if not uid or uid not in self._order:
            raise ValueError('cannot find record to move for id %s' % uid)
        self._order.insert(offset, self._order.pop(self._order.index(uid)))
    
    def updateOrder(self, order):
        """Provides zope.container.interfaces.IOrdered.updateOrder"""
        if len(order) != len(self._order):
            raise ValueError('invalid number of keys')
        s_order = set(order)
        if len(order) != len(s_order):
            raise ValueError('duplicate keys in order')
        if s_order - set(self._order):
            raise ValueError('unknown key(s) provided in order')
        if not isinstance(order, PersistentList):
            order = PersistentList(order)
        self._order = order
    
    # IReadContainer interface methods:
    
    def get(self, uid, default=None):
        """
        Get object providing IRecord for given UUID uid or return None
        """
        if self.RECORD_INTERFACE.providedBy(uid):
            uid = uid.record_uid  #special case to support __contains__() impl
        return self._entries.get(str(uid), default)
    
    def __contains__(self, record):
        """
        Given record as either IRecord object or UUID, is record contained?
        """
        if self.RECORD_INTERFACE.providedBy(record):
            return self.get(record, None) is not None
        return str(record) in self._entries
    
    def __len__(self):
        """ return length of record entries """
        return len(self._order) #more efficient vs. len(self._entries) usually
    
    def __getitem__(self, key):
        """Get item by UID key"""
        v = self.get(key, None)
        if v is None:
            raise KeyError('unknown UID for record entry')
        return v
    
    def keys(self):
        """return tuple with elements ordered"""
        return tuple(self._order)
    
    def values(self):
        """return tuple of records in order"""
        return tuple([t[1] for t in self.items()])
    
    def items(self):
        """return ordered pairs of key/values"""
        return tuple([(uid, self._entries[uid]) for uid in self._order])
    
    def __iter__(self):
        return self._order.__iter__()
    
    # IRecordContainer-specific CRUD methods:
    
    def _type_whitelist_validation(self, value):
        vtype = type(value)
        if vtype in self.MAPPING_WHITELIST:
            for k,v in v.items():
                if not (k in self.TYPE_WHITELIST and v in self.TYPE_WHITELIST):
                    raise ValueError('Unsupported mapping key/value type')
        elif vtype in self.SEQUENCE_WHITELIST:
            for v in value:
                if v not in self.TYPE_WHITELIST:
                    raise ValueError('Unsupported sequence value type')
        else:
            if vtype not in self.TYPE_WHITELIST:
                raise ValueError('Unsupported data type')
    
    def _populate_record(self, record, data):
        """
        Given mapping of data, copy values to attributes on record.
        
        Subclasses may override to provide schema validation, selective
        copy of names, and normalization of values if/as necessary.
        """
        changelog = []
        for key,value in data.items():
            if key.startswith('_'):
                continue #invalid key
            if key == 'record_uid':
                self.record_uid = str(value)
                continue
            try:
                self._type_whitelist_validation(value)
            except ValueError:
                continue #skip problem name!
            existing_value = getattr(self, key, None)
            if value != existing_value:
                changelog.append(key)
                setattr(record, key, value)
        if changelog:
            record._p_changed = True
            changelog = [Attributes(self.RECORD_INTERFACE, name)
                            for name in changelog]
            notify(ObjectModifiedEvent(record, *changelog))
    
    def create(self, data=None):
        """
        Alternative factory for an IRecord object, does not store object.
        If data is not None, copy fields from data.
        """
        if data is None:
            data = {}
        uid = data.get('record_uid', str(uuid.uuid4())) #get or random uuid
        record = self.factory(context=self, uid=uid)
        if data and (hasattr(data, 'get') and 
                     hasattr(data, 'items')):
            self._before_populate(record, data)
            self._populate_record(record, data)
        notify(ObjectCreatedEvent(record))
        return record
    
    def add(self, record):
        """
        Add a record to container, append UUID to end of order; over-
        write existing entry if already exists for a UUID (in such case
        leave order as-is).
        """
        uid = str(record.record_uid)
        if not uid:
            raise ValueError('record has empty UUID')
        self._entries[uid] = record
        if uid not in self._order:
            self._order.append(uid)
        notify(ObjectAddedEvent(record, self, uid))
    
    def _ad_hoc_fieldlist(self, record):
        uid = record.record_uid
        attrs = [name for name in dir(record) if not name.startswith('_')]
        fieldnames = []
        for name in attrs:
            v = getattr(record, name)
            try:
                self._type_whitelist_validation(v)
                fieldnames.append(name)
            except ValueError:
                pass #ignore name
        return fieldnames
    
    def _filtered_data(self, data):
        fieldnames = self._ad_hoc_fieldlist(data)
        return dict([(k, getattr(data, k, None)) for k in fieldnames])
    
    def _before_populate(self, record, data):
        pass #hook for subclasses
    
    def _before_update_notification(self, record, data):
        pass #hook for subclasses
    
    def update(self, data, suppress_notify=False):
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
        if self.RECORD_INTERFACE.providedBy(data):
            uid = data.record_uid
            data = self._filtered_data(data)
        else:
            uid = data.get('record_uid', None)
        if uid is None:
            raise ValueError('empty record UID on update')
        uid = str(uid)
        record = self.get(uid, None)
        if record is not None:
            # existing record, already known/saved
            self._before_populate(record, data)
            self._populate_record(record, data) # also notifies modified event
        else:
            # new, create, then add
            record = self.create(data)  # notifies created, modified events
            self.add(record)            # notified added event
        self._before_update_notification(record, data)
        if (not suppress_notify) and getattr(record, '_p_changed', None):
            notify(ObjectModifiedEvent(self))
        return record

    def _process_container_metadata(self, data):
        return False #hook for subclasses
    
    def update_all(self, data):
        """
        Given sequence of data dictionaries or a JSON serialization
        thereof, update each item.  Raises ValueError on missing UID of
        any item/entry.  Also supports JSON serialization of a single
        record/entry dict.
        """
        _modified = False
        if isinstance(data, basestring):
            _data = json.loads(data)
            if isinstance(_data, dict):
                # dict might be singluar item, or wrapping object; a wrapping
                # object would have a list called 'entries'
                if 'entries' in _data and isinstance(_data['entries'], list):
                    _modified = self._process_container_metadata(_data)
                    #wrapper, get entries from within.
                    _data = _data['entries']
                else:
                    #singular record, not a wrapper
                    _data = [_data] #wrap singular item update in list
            _keynorm = lambda o: dict([(str(k), v) for k,v in o.items()])
            data = [_keynorm(o) for o in _data]
            uids = [str(o['record_uid']) for o in data]
        for entry_data in data:
            if 'record_uid' not in entry_data:
                raise ValueError('record missing UID')
            record = self.update(entry_data, suppress_notify=True)
            if not _modified and getattr(record, '_p_changed', None):
                _modified = True
        remove_uids = set(self.keys()) - set(uids)
        for deluid in remove_uids:
            del(self[deluid]) #remove any previous entries not in the form
        self._order = PersistentList(uids) #replace old with new uid order
        if data and _modified:
            notify(ObjectModifiedEvent(self)) # notify only once!


class BTreeRecordContainer(RecordContainer):
    """Record container uses OOBTree for entry storage"""
    
    def __init__(self, _impl=OOBTree):
        super(BTreeRecordContainer, self).__init__(_impl)


