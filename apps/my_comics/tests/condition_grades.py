from apps.my_comics.statics import condition_grade_scales

import unittest

class ConditionGradesTestCase(unittest.TestCase):
    def test_compare(self):
        print "testing ConditionGradesTestCase.compare"
        self.assertTrue(
            condition_grade_scales['a']['anm'] >
                        condition_grade_scales['a']['apr'])

if __name__ == '__main__':
    unittest.main()
