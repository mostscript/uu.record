Introduction
============

uu.record manages record objects inside a content management system using
the ZODB, Zope Component Architecture, and the Zope CMF frameworks.
Records are just uniquely locatable and identifiable objects.

uu.record is a library for managing persistent data record objects within a
Zope CMF (or Plone) context.  This library provides base interfaces for 
record objects and utility and adpapter components related to them, with 
some basic key assumptions:

  1. Records have unique ids -- specifically RFC 4122 UUIDs -- at a known
     reliable attribute/property name directly accessible on the object.
     
        * For simplicity, presented as attribute in string representation.

        * The simplicity of string format is usually a pragmatic win over
          the storage/comparison optimization of storing binary UUIDs.

        * Implementations may use properties or descriptors to store 
          binary (uuid.UUID) objects and present callers with string
          format.

  2. Records have some adaptation context or contained 'placeful' location
     in some software / data-management system.  Therefore, records should
     implement zope.location.interfaces.ILocation with:

        * a __parent__ attribute pointing to the container or context
          that is managing the record.  The key assumption here is that
          records are 'managed' by some external controller or container
          that is responsible for some aspect of CRUD operations on the
          records contained within.

  3. Records are typically contained in a mapping-like container, which
     may be (and usually is) ordered.

  4. Records need to be resolvable by their UUID from any context within
     a software system (or within a "site" / application).  This is a
     necessary condition for many information retrieval functions.

  5. It should be possible to index records keyed by their UUID in
     some system.  Since many search/index/catalog systems use integer
     ids for returned results of a query, it may make sense to maintain
     a mapping utility that is a two-way index of UUIDs to integer ids.

  6. Records, at their core, are schema-less.  Higher-level frameworks
     may impose schema on instances or containers, but the core
     operations of records can operate without schema dictating fields
     contained within.  Records are just uniquely locatable and 
     identifiable objects.


License
-------

This is a framework-level component that does not depend on upstream GPL
code; as such it is licensed under an MIT-style open-source license that
is compatible with the GNU GPL v2 used in many packages inside Plone.

All GPL-dependent code using this framework should be packaged in products
and libraries using this package, not within it.

--

Author: Sean Upton <sean.upton@hsc.utah.edu>

Copyright 2011, The University of Utah.

Released as free software under an MIT-style license, please see 
docs/COPYING.txt within this package for details of the license.

