"""
schemainfo.py: tools for metadata stubs about schema and fields, and tools
to resolve schema by name/identifier.

Usage
-----

    Get the global site manager for dealing with components:
    
    >>> from zope.component import getGlobalSiteManager
    >>> gsm = getGlobalSiteManager()
    
    Get a schema or some interface with schema fields using an (arbitrary)
    interface class in this package known to have zope.schema fields:
    
    >>> from uu.record.interfaces import IRecord
    >>> assert 'record_uid' in IRecord      # a field we can reference
    
    Register an interface resolver for dotted names:
    
    >>> from uu.record.query.interfaces import ISchemaResolver
    >>> from uu.record.query.schemainfo import DottedNameInterfaceResolver

    Initially, there is no utility to resolve an interface from a dotted name:
    
    >>> dotted_name = IRecord.__identifier__
    >>> assert dotted_name == 'uu.record.interfaces.IRecord'
    >>> from zope.component import queryUtility
    >>> resolver = queryUtility(ISchemaResolver, name='dottedname')
    >>> assert resolver is None
    
    Get a SchemaInfo object for an arbitrary context object:
    
    >>> from uu.record.query.interfaces import ISchemaInfo, IFieldInfo
    >>> from uu.record.query.schemainfo import SchemaInfo
    >>> context = object()
    >>> info = SchemaInfo(context, IRecord)
    >>> assert info.context is context
    >>> assert ISchemaInfo.providedBy(info)
    
    Initially, calling the schema info object does not resolve the interface,
    due to a lack of resolver utility registration:
    
    >>> assert hasattr(info, '__call__')
    >>> assert info() is None
    
    Likewise, attempting to call a field info object that depends on the 
    schema info object to resolve a field will fail without such resolver
    registered:
    
    >>> for fieldname, field in getFieldsInOrder(IRecord):
    ...     fieldinfo = [fi for fi in info.fields if fi.name==fieldname][0]
    ...     assert fieldinfo() is None # no way to resolve field if not schema!
    ... 
    
    If we register the dotted name resolver, we get better results from call:
    
    >>> gsm.registerUtility(factory=DottedNameInterfaceResolver,
    ...                     provided=ISchemaResolver,
    ...                     name='dottedname')
    >>> resolver = queryUtility(ISchemaResolver, name='dottedname')
    >>> assert resolver is not None
    >>> assert resolver(dotted_name) is IRecord #retrieved by name!
    >>> assert hasattr(info, '__call__')
    >>> assert info() is IRecord  #now this works!
    
    List fields and demonstrate that we have the fields we expect -- calling
    a field info object will resolve the field itself:
    
    >>> for fieldinfo in info.fields:
    ...     assert IFieldInfo.providedBy(fieldinfo)
    ...     assert fieldinfo.name in IRecord
    ...     assert IRecord[fieldinfo.name] is fieldinfo()
    ... 
    >>> assert 'record_uid' in [fi.name 
    ...                             for fi in info.fields] #field we know about
    >>> from zope.schema import getFieldsInOrder
    >>> from zope.schema.interfaces import IBytes #index: default ignored
    >>> for fieldname, field in getFieldsInOrder(IRecord):
    ...     fieldinfo = [fi for fi in info.fields if fi.name==fieldname][0]
    ...     assert fieldinfo() is field
    ...     if not IBytes.providedBy(field):
    ...         assert fieldinfo.indexes #non-empty
    ... 
    
    Finally, we can register SchemaInfo as a multi-adapter for any arbitrary
    context and some schema (providing IInterface):
    
    >>> from zope.interface import Interface #any object provides this
    >>> from zope.interface.interfaces import IInterface
    >>> gsm.registerAdapter(factory=SchemaInfo, provided=ISchemaInfo)
    >>> from zope.component import getMultiAdapter
    >>> assert isinstance(getMultiAdapter((None, IRecord), ISchemaInfo),
    ...                   SchemaInfo)
    >>> 

"""

from zope.component import adapts, queryUtility
from zope.dottedname.resolve import resolve
from zope.interface import Interface, implements, providedBy
from zope.interface.interfaces import IInterface
import zope.schema.interfaces
from zope.schema.interfaces import IField
from zope.schema import getFieldsInOrder

from uu.record.query.interfaces import IFieldInfo, ISchemaInfo
from uu.record.query.interfaces import ISchemaResolver


is_an_ifield = lambda iface: issubclass(iface, IField) and not iface is IField
field_types = lambda f: [i for i in providedBy(f) if is_an_ifield(i)]


def field_index_types(fieldinfo):
    if isinstance(fieldinfo.fieldtype, zope.schema.interfaces.ICollection):
        field = fieldinfo() # resolve field instance
        if (zope.schema.IText.providedBy(field.value_type) or 
                zope.schema.IBytesLine.providedBy(field.value_type)):
            return ('keyword',) #collection of text: keyword index
    
    idxmap = {
        zope.schema.interfaces.ITextLine     : ('field', 'text'),
        zope.schema.interfaces.IBytesLine    : ('field', 'text'),
        zope.schema.interfaces.IText         : ('text',),
        zope.schema.interfaces.IBytes        : (), #omit bytes fields!
        }
    if fieldinfo.fieldtype in idxmap:
        idxtypes = idxmap[fieldinfo.fieldtype]
    else:
        idxtypes = ('field',) #default
    return idxtypes


def field_index_name(idxtype, fieldinfo):
    """given index type and field info, return a string name"""
    if isinstance(fieldinfo.fieldtype, zope.schema.interfaces.ICollection):
        field = fieldinfo() # resolve field instance
        fieldtype = field.value_type.__name__
    else:
        fieldtype = fieldinfo.fieldtype.__name__
    return '.'.join((idxtype, fieldtype, fieldinfo.name,))


class DottedNameInterfaceResolver(object):
    """Resolver utility for getting interfaces by dotted name"""
    
    implements(ISchemaResolver)
    
    def __call__(self, name):
        try:
            iface = resolve(name)
            if not IInterface.providedBy(iface):
                return None
            return iface
        except ImportError:
            return None


class FieldInfo(object):
    """
    Metadata about a schema field
    """
    
    implements(IFieldInfo)
    
    def __init__(self, context, field, **kwargs):
        if not ISchemaInfo.providedBy(context):
            raise ValueError('ISchemaInfo must be provided by context')
        if not zope.schema.interfaces.IField.providedBy(field):
            raise ValueError('field for FieldInfo must provide IField')
        self.context = context  # SchemaInfo object
        self._load_field_metadata(field)
    
    def _load_field_metadata(self, field):
        self.name = field.__name__
        self.title = field.title
        self.description = field.description
        self.fieldtype = field_types(field)[0]
        self._add_index_names()
    
    def _add_index_names(self):
        #import pdb; pdb.set_trace()
        self.indexes = []
        idxtypes = field_index_types(self)
        for idxtype in idxtypes:
            self.indexes.append(field_index_name(idxtype, self))
    
    def __call__(self):
        iface = self.context()
        if iface is None:
            return None
        if self.name not in iface:
            return None
        return iface[self.name]


class SchemaInfo(object):
    """
    A metadata stub for a schema object and multi-adapter for:
    
        (a) some application context, stored as self.context
        
        (b) a schema/interface object; a direct reference to the adapted
            schema is not stored after construction, only a resolvable
            name of the schema object, which can be fetched by calling
            a SchemaInfo object.
    
    Adapter for a schema object providing ISchemaInfo metadat about that
    schema.  Used to hold metadata about a schema without a direct reference
    to that schema/interface object.
    
    Resolving interfaces by __call__() uses one or more named
    ISchemaResolver utilities.
    
    Applications may subclass this adapter to override name resolution:
        
        * Application subclasses should override __call__()
        
        * Application subclasses should override _load_schema_name()
    
    """
    
    implements(ISchemaInfo)
    
    adapts(Interface, IInterface)
    
    def __init__(self, context, schema):
        if not IInterface.providedBy(schema):
            raise ValueError('cannot adapt, context is not an interface')
        self.context = context
        self._load_schema_name(schema)
        self._load_schema_fields(schema)
        self.indexes = [] #initially empty; intended to be set by callers.
    
    def _load_schema_name(self, schema):
        self.namespace = 'dotted'
        self.name = getattr(schema, '__identifier__') #dotted name default

    def _load_schema_fields(self, schema):
        self.fields = []
        for fieldname, field in getFieldsInOrder(schema):
            self.fields.append(FieldInfo(self, field))
    
    def __call__(self):
        if self.namespace != 'dotted':
            return None
        resolver = queryUtility(ISchemaResolver, name='dottedname')
        if resolver is None:
            return None
        return resolver(self.name)

