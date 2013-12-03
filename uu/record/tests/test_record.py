import doctest
import unittest2 as unittest
import uu.record.base


def test_suite():
    suite = unittest.TestSuite()
    suite.addTests([doctest.DocTestSuite(uu.record.base)])
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())

