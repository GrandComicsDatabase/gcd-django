# -*- coding: utf-8 -*-
from models import ConditionGrade, ConditionGradeScale

#The idea below is to be able to recognize key for condition_grade_scales
# dictionary while having key for dictionary in ConditionGradeScale object. And
# it is to be done by prefixing keys in those dictionaries with key from
# condition_grade_scales.
# E.g. having a key 'bvf' (which will be kept in CollectionItem) it will be
# easy to know that it is connected to grade from scale kept under key 'b' -
# 'US ten-point grading scale'.
condition_grade_scales = \
  {'a':ConditionGradeScale('a', 'US basic grading scale',
            {'anm':ConditionGrade('NM', 'Near Mint', 8),
             'avf':ConditionGrade('VF', 'Very Fine', 7),
             'afn':ConditionGrade('FN', 'Fine',      6),
             'afg':ConditionGrade('FG', 'Very Good', 5),
             'agd':ConditionGrade('GD', 'Good',      4),
             'afr':ConditionGrade('FR', 'Fair',      3),
             'apr':ConditionGrade('PR', 'Poor',      2),
            }),
   'b':ConditionGradeScale('b', 'US ten-point grading scale',
            {'bgm':ConditionGrade('GM', 'Gem Mint', 10),
             'bm':ConditionGrade('M', 'Mint', 9.9),
             'bnm/m':ConditionGrade('NM/M', 'Near Mint/Mint', 9.8),
             'bnm+':ConditionGrade('NM+', 'Near Mint+', 9.6),
             'bnm':ConditionGrade('NM', 'Near Mint', 9.4),
             'bnm-':ConditionGrade('NM-', 'Near Mint-', 9.2),
             'bvf/nm':ConditionGrade('VF/NM', 'Very Fine/Near Mint', 9.0),
             'bvf+':ConditionGrade('VF+', 'Very Fine+', 8.5),
             'bvf':ConditionGrade('VF', 'Very Fine', 8.0),
             'bvf-':ConditionGrade('VF-', 'Very Fine-', 7.5),
             'bfn/vf':ConditionGrade('FN/VF', 'Fine/Very Fine', 7.0),
             'bfn+':ConditionGrade('FN+', 'Fine+', 6.5),
             'bfn':ConditionGrade('FN', 'Fine', 6.0),
             'bfn-':ConditionGrade('FN-', 'Fine-', 5.5),
             'bvg/fn':ConditionGrade('VG/FN', 'Very Good/Fine', 5.0),
             'bvg+':ConditionGrade('VG+', 'Very Good+', 4.5),
             'bvg':ConditionGrade('VG', 'Very Good', 4.0),
             'bvg-':ConditionGrade('VG-', 'Very Good-', 3.5),
             'bgd/vg':ConditionGrade('GD/VG', 'Good/Very Good', 3.0),
             'bgd+':ConditionGrade('GD+', 'Good+', 2.5),
             'bgd':ConditionGrade('GD', 'Good', 2.0),
             'bgd-':ConditionGrade('GD-', 'Good-', 1.8),
             'bfr/gd':ConditionGrade('FR/GD', 'Fair/Good', 1.5),
             'bfr':ConditionGrade('FR', 'Fair', 1.0),
             'bpr':ConditionGrade('PR', 'Poor', 0.5),
            }),
    'c':ConditionGradeScale('c', 'German grading scale',
            {'cz0':ConditionGrade('Zustand 0','perfekt',10),
             'cz01':ConditionGrade('Zustand 0-1','fast perfekt',9),
             'cz1':ConditionGrade('Zustand 1','sehr gut',8),
             'cz12':ConditionGrade('Zustand 1-2','fast sehr gut',7),
             'cz2':ConditionGrade('Zustand 2','gut',6),
             'cz23':ConditionGrade('Zustand 2-3','noch recht gut',5),
             'cz3':ConditionGrade('Zustand 3','noch sammelwürdig',4),
             'cz34':ConditionGrade('Zustand 3-4','schlecht',3),
             'cz4':ConditionGrade('Zustand 4','zum Wegwerfen zu schade',2),
             'ce':ConditionGrade('Zustand 5','unvollständig',1),
            }),
  }
