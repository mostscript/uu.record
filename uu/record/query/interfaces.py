from zope.interface import Interface
from zope.interface.interfaces import IInterface
from zope import schema


class ISchemaResolver(Interface):
    """
    Utility component to resolve a schema by name
    
    Recommended: register named utilities looked up by the name of the
                 naming strategy (e.g. 'dottedname', 'md5sum') for the 
                 interface.  Interfaces implemented in Python code
                 will likely be best resolved by dotted name, though
                 other strategies may be appropriate for different
                 application use cases.
    """
    
    def __call__(self, name):
        """
        Attempt to resolve schema/interface object given a name.
        
        Returns None on unresolved schema/interface object.
        """


class IFieldInfo(Interface):
    """general metadata about a schema field"""
    
    name = schema.BytesLine()
    
    title = schema.TextLine()
    
    description = schema.Text()
    
    fieldtype = schema.Object(
        title=u'Field type',
        description=u'The interface that the field provides.',
        schema=IInterface,
        constraint=lambda v: isinstance(v, IField),
        )
    
    indexes = schema.List(
        title=u'Indexes',
        description=u'Indexes related to this field',
        value_type=schema.BytesLine(title=u'Index name'),
        defaultFactory=list,
        required=True,
        )
    
    context = schema.Object(
        title=u'Context',
        description=u'Context object providing ISchemaInfo',
        schema=Interface,
        required=False,
        )
    
    def __call__():
        """
        Resolve field object instance using self.context; if self.context
        is None, return None.  self.context may be None, but calling
        a non-None self.context (an ISchemaInfo object) may also return
        None for resolution of a field necessary; in such case, this
        method may return None as well.
        """


class ISchemaInfo(Interface):
    """
    A metadata wrapper and object resolver for a schema.  May be used
    as an interface to adapt any schema.
    """
    
    name = schema.BytesLine(
        title=u'Schema name',
        description=u'Dotted name of interface, or md5 signature of '\
                    u'serialization.',
        required=True,
        )
    
    namespace = schema.BytesLine(
        title=u'Namespace',
        description=u'Namspace/kind of schema identifier/name.',
        required=True,
        default='dottedname',
        )
    
    context = schema.Object(
        title=u'Context',
        description=u'Context object, may be catalog.',
        schema=Interface,
        required=False,
        )
    
    fields = schema.List(
        value_type=schema.Object(schema=IFieldInfo),
        defaultFactory=list,
        required=True,
        )
    
    indexes = schema.List(
        title=u'Indexes',
        description=u'Index names related to this schema',
        value_type=schema.BytesLine(title=u'Index name'),
        defaultFactory=list,
        required=True,
        )
    
    def __call__():
        """
        Resolve reference to schema/interface object providing IInterface
        and all fields advertised here, for the given schema name/identifier.
        
        May delegate to other application/framework specific components
        including (but not limited to) application-specific ISchemaResolver
        utilities.
        
        Implementations may delegate in series to multiple named
        ISchemaResolver components, which may have names like 'dottedname'
        or 'md5sum'.
        
        Returns None if no interface can be resolved, or if no suitable
        ISchemaResolver component can be found.
        """


IFieldInfo['context'].schema = ISchemaInfo #workaround order of definition


class IQuery(Interface):
    """
    Marker for a class providing a query part/operator; note it is the 
    class of operator, not instances thereof, that provide this interface.
    """


class IBooleanOperator(IQuery):
    """
    Boolean operator combines queries.
    """
    
    __name__ = schema.BytesLine(title=u'Name', readonly=True)
    
    def __call__(*queries):
        """Combine queries"""


class IComparator(IQuery):
    """
    Comparison operator class used to evaluate an index against a value, used
    as a specification for query by catalog search execution.
    """
    
    __name__ = schema.BytesLine(title=u'Name', readonly=True)
    
    def __call__(index_name, *args, **kwargs):
        """
        Call filter for use in searching, for most comparators, a single
        argument of 'value' is provided; however, more complex comparisons
        may exist (e.g. a range search).
        """


DEFAULT_GETUID = lambda record: getattr(record, 'uid', str(uuid.uuid4()))

class IRecordCatalog(Interface):
    
    mapper = schema.Object(
        title=u'Document mapper',
        description=u'UUID/integer document id mapper and metadata storage. '\
                    u'Implementations are assumed interface-compatible with '\
                    u'repoze.catalog.document.DocumentMap class API.',
        schema=Interface,
        required=True,
        )
    
    indexer = schema.Object(
        title=u'Indexer',
        description=u'Catalog of indexes, assumed interface-compatible with '\
                    u'repoze.catalog.catalog.Catalog class API.',
        schema=Interface,
        required=True,
        )
    
    supported = schema.List(
        title=u'List of supported schema',
        value_type=schema.Object(schema=ISchemaInfo),
        )
    
    def getObject(identifier):
        """
        Given an identifier as either a UID mapped in self.mapper or an
        integer id key from self.indexer, resolve object or return None.
        """
    
    def bind(schema, omit=(), index_types=None):
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
    
    def unbind(schema, remove_indexes=False):
        """
        Unbind a schema providing IInterface or object providing ISchemaInfo,
        removing it from self.supported.
        
        If remove_indexes is True (by default, it is False), then remove any
        indexes for which the schema in question is the only schema in the 
        catalog managing any respective index name.
        """
    
    def searchable(schema):
        """
        Return a tuple of IFieldInfo objects, which provide the names of fields
        with respective indexes.  Fields without indexes will not have an
        IFieldInfo object returned.
        """
    
    def uniqueValuesFor(index):
        """
        Given index name, get unique values for content stored in the 
        'forward index' inside the catalog for that index object.
        
        If index name is not in the catalog, raise KeyError.
        
        If index in catalog for the index name is a text index (incapable
        of providing unique values), raise a ValueError.
        """
    
    def comparatorsFor(index):
        """
        Return tuple of available comparator functions and their labels. 
        Output is a tuple of two-item tuples, where the first item is
        a comparator function or class providing IComparator, and the
        second item is a human-readable label for that comparator.
        """
    
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
    
    def unindex(uid):
        """
        Given the UUID (uid) of a record as either a uuid.UUID object or as
        a string representation of UUID, remove the record from self.indexer
        and self.mapper.
        """
    
    def reindex(record, uid=None, getuid=DEFAULT_GETUID):
        """
        Alternate spelling for index(), may be optimized in implementation
        or may simply just provide a synonymous call.
        """
    
    def __getitem__(name):
        """return index for name from self.indexer, or raise KeyError"""
    
    def get(name, default=None):
        """return index for name from self.indexer, default, or None"""

    def __setitem__(name, index):
        """
        Set an index object into self.indexer explicitly; prefer
        self.bind(schema) for adding indexes based on zope.schema fields
        over this.
        """
    
    def search(**query):
        """
        Given a search as index-name/value mapping, return a results in the
        form (count, iterable of result uids).
        """
    
    def query(query, *args, **kwargs):
        """
        Given a search as a query providing IQuery, return a results in the
        form (count, iterable of result uids).
        
        Additional arguments are implementation-specific, and may be used
        for sorting results.  Each implementation should gracefully ignore
        arguments it does not know about.
        """




