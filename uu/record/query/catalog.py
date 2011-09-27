from persistent import Persistent
from persistent.dict import PersistentDict
from persistent.list import PersistentList
from zope.component import queryUtility, getMultiAdapter
from zope.interface import implements
from zope import schema
import repoze.catalog
from repoze.catalog.catalog import Catalog
from repoze.catalog.document import DocumentMap

from uu.record.query.interfaces import IRecordCatalog, ISchemaInfo
from uu.record.interfaces import IRecordResolver


class RecordCatalog(Persistent):
    """
    Record catalog is facade for repoze.catalog backend providing 
    IRecordCatalog front-end.
    """
    
    implements(IRecordCatalog)
    
    def __init__(self, name=None):
        self.name = name
        self.indexer = Catalog()
        self.mapper = DocumentMap()
        self.supported = PersistentDict() #schema id/name->ISchemaInfo
        self._index_owners = PersistentDict() # idx name->list of schema names
    
    def getObject(self, identifier):
        """
        Given an identifier as either a UID mapped in self.mapper or an
        integer id key from self.indexer, resolve object or return None.
        """
        if isinstance(identifier, int):
            identifier = self.mapper.address_for_docid(identifier) #int->uuid
        resolver = queryUtility(IRecordResolver)
        if resolver is None:
            return None
        return resolver()
    
    def _add_index(self, idxname, idxtype, getter=None):
        if getter is None:
            getter = lambda obj, name, default: getattr(obj, name, default)
        callback = lambda obj, default: getter(obj, idxname, default)
        idxcls = {
            'field'     : repoze.catalog.indexes.field.CatalogFieldIndex,
            'text'      : repoze.catalog.indexes.text.CatalogTextIndex,
            'keyword'   : repoze.catalog.indexes.keyword.CatalogKeywordIndex,
            }[idxtype]
        self.indexer[idxname] = idxcls(callback)
    
    def bind(self, schema, omit=(), index_types=None):
        """
        Bind a schema providing IInterface.
        
        An object providing ISchemaInfo will be created and stored in
        self.supported.
        
        All fields in the schema will have coresponding indexes created for
        them (unless a fieldname is provided in the omit argument sequence)
        in self.indexer.  All index names created will be saved to the 
        ISchemaInfo object being saved in self.supported.
        
        The index type for any field will, by default, be determined by the
        type of the field.  If the field is a sequence, by default, the
        index type will be a 'keyword' index.  If the value type is a
        TextLine or BytesLine, then *both* 'text' and 'field' indexes will
        be created for that field.  If the value type is Text (multi-line
        text), then only a (full) 'text' index will be created.
        
        If the field is a Bytes field, we cannot tell whether this field is
        tokenizable text, so we omit Bytes fields by default.  However, 
        since BytesLine fields are constrained by textual cues (absense of
        line feeds), we index BytesLine as field and text values.  This is
        a sensible default behavior, considering some Bytes fields may
        contain large size binary content we do not want to index.
        
        Index types can be specified by providing a dict/mapping of 
        field name keys to index type values.  Such values can be provided
        to override index creation defaults as any of:
        
            * A string name in ('field', 'text', 'keyword')
        
            * sequence (set/tuple/list) of one or more of the above names,
              except None is mutually exclusive with other choices.
        
            * None: equivalent to omitting field using the omit argument.
        
        Overrides of index_types should not declare incorrect index types
        for a field; the following should raise a ValueError:
        
            * Specifying a text index on a non-text field, even if the 
                value can be cast to a string, it has no reasonable hope
                of being either meaningful or tokenized in the vast
                majority of cases.  
                
                * Optimistic exception: allow any sequence field for which
                  a value type contains text or bytes based fields.
        
            * Specifying a keyword index on a non-sequence field.
        """
        # adapt context, schema: produces schema+field info with index
        # names populated for use here.
        info = getMultiAdapter((self, schema),
                               ISchemaInfo) #adapt context, schema
        _marker = object()
        for fieldinfo in info.fields:
            for idxname in fieldinfo.indexes:
                idxtype = idxname.split('.')[0]
                if idxname not in self.indexer:
                    self._add_index(idxname, idxtype)
                    if idxname not in self._index_owners:
                        self._index_owners[idxname] = PersistentList()
                    self._index_owners[idxname].append(info.name)
        self.supported[info.name] = info
    
    def unbind(self, schema, remove_indexes=False):
        """
        Unbind a schema providing IInterface or object providing ISchemaInfo,
        removing it from self.supported.
        
        If remove_indexes is True (by default, it is False), then remove any
        indexes for which the schema in question is the only schema in the 
        catalog managing any respective index name.
        """
        info = getMultiAdapter((self, schema),
                               ISchemaInfo) #adapt context, schema
        if info.name in self.supported:
            del(self.supported[name])
            if remove_indexes:
                for idxname in info.indexes:
                    if idxname in self.indexer:
                        owners = self._index_owners.get(idxname, ())
                        if len(owners)==1 and info.name in owners:
                            del(self.indexer[idxname])
                            del(self._index_owners[idxname])
    
    def searchable(self, schema):
        """
        Return a tuple of IFieldInfo objects, which provide the names of fields
        with respective indexes.  Fields without indexes will not have an
        IFieldInfo object returned.
        """
        raise NotImplementedError('TODO') #TODO TODO TODO
    
    def uniqueValuesFor(index):
        """
        Given index name, get unique values for content stored in the 
        'forward index' inside the catalog for that index object.
        
        If index name is not in the catalog, raise KeyError.
        
        If index in catalog for the index name is a text index (incapable
        of providing unique values), raise a ValueError.
        """
        raise NotImplementedError('TODO') #TODO TODO TODO
    
    def comparatorsFor(index):
        """
        Return tuple of available comparator functions and their labels. 
        Output is a tuple of two-item tuples, where the first item is
        a comparator function or class providing IComparator, and the
        second item is a human-readable label for that comparator.
        """
        raise NotImplementedError('TODO') #TODO TODO TODO
    
    def index(record, uid=None, getuid=DEFAULT_GETUID):
        """
        Given a record object providing any number of interfaces, index that
        record's field values for all interfaces it provides that are also
        supported by this catalog.  The record must have a UUID, which can
        be provided by value using the uid parameter, or looked up from the
        record object using a getuid function/callable.  The default 
        should be to obtain a 'uid' attribute/property value from the 
        record object itself.
        
        uid provided (or obtained) should be either:
        
            * A 36-byte string representation of the UUID
            
            * A uuid.UUID object.
        
        If no UUID is provided nor resolved by function, raise a ValueError.
        Note: the default getuid function will get a random UID for the 
        record if None can be found.
        
        Note: self.mapper will store string representations of the UUID.
        
        Returns the string representation of the UUID of the document, useful
        if the UUID was generated byt the getuid function passed to index.
        
        Implicit path/location indexing: if the record object provides
        zope.location.interfaces.ILocation, then index the object's
        identifier (__name__) and container (__parent__) in field and path
        indexes respectively.
        """
        raise NotImplementedError('TODO') #TODO TODO TODO
    
    def unindex(uid):
        """
        Given the UUID (uid) of a record as either a uuid.UUID object or as
        a string representation of UUID, remove the record from self.indexer
        and self.mapper.
        """
        raise NotImplementedError('TODO') #TODO TODO TODO
    
    def reindex(record, uid=None, getuid=DEFAULT_GETUID):
        """
        Alternate spelling for index(), may be optimized in implementation
        or may simply just provide a synonymous call.
        """
        raise NotImplementedError('TODO') #TODO TODO TODO
    
    def __getitem__(name):
        """return index for name from self.indexer, or raise KeyError"""
        raise NotImplementedError('TODO') #TODO TODO TODO
    
    def get(name, default=None):
        """return index for name from self.indexer, default, or None"""
        raise NotImplementedError('TODO') #TODO TODO TODO

    def __setitem__(name, index):
        """
        Set an index object into self.indexer explicitly; prefer
        self.bind(schema) for adding indexes based on zope.schema fields
        over this.
        """
        raise NotImplementedError('TODO') #TODO TODO TODO
    
    def search(**query):
        """
        Given a search as index-name/value mapping, return a results in the
        form (count, iterable of result uids).
        """
        raise NotImplementedError('TODO') #TODO TODO TODO
    
    def query(query, *args, **kwargs):
        """
        Given a search as a query providing IQuery, return a results in the
        form (count, iterable of result uids).
        
        Additional arguments are implementation-specific, and may be used
        for sorting results.  Each implementation should gracefully ignore
        arguments it does not know about.
        """
        raise NotImplementedError('TODO') #TODO TODO TODO

