
from zope.interface import implements
from zope.component.hooks import getSite
from Products.CMFCore.utils import getToolByName

from uu.record.interfaces import IRecordResolver


class CatalogRecordResolver(object):
    """
    Resolve record object by finding its parent using Plone catalog search
    of a KeywordIndex for contained UIDs of records.
    
    Assumption is that a context is looked up, and that that context
    provides IItemMapping or zope.container.interfaces.IReadContainer; this
    assumption isn't checked, we just duck-type assuming any context that
    looks like a mapping, and has a get() method taking a key.
    """
    
    implements(IRecordResolver)
    
    INDEX_NAME = 'contained_uids' #needs to be KeywordIndex in portal_catalog
    loaded = False
    
    def _load_globals(self):
        self.portal = getSite()
        self.catalog = getToolByName(self.portal, 'portal_catalog')
        self.loaded = True
    
    def __call__(self, uid, _context=None):
        if not self.loaded:
            self._load_globals()
        if _context is None:
            _context = self.context(uid)
        return _context.get(uid, None)
    
    def context(self, uid):
        if not self.loaded:
            self._load_globals()
        brains = self.catalog.query({INDEX_NAME: str(uid)})
        if brains:
            return brains[0].getObject() #first location should be only.
        return None
    
    def contained(self, uid):
        if not self.loaded:
            self._load_globals()
        context = self.context(uid)
        if context is None:
            return (None, None)
        return (context, self(uid, context))

