"""
Due to uncertainty about how to best structure things and the size of the app,
the models and views were split into multiple individual files instead of
the traditional models.py and views.py files.
"""

# Make imports work as if we just had a single "models.py" file.

from .publisher import Publisher, IndiciaPublisher, Brand, BrandGroup, BrandUse
from .series import Series, SeriesPublicationType
from .issue import Issue, INDEXED
from .story import StoryType, Story, CreditType, StoryCredit, BiblioEntry,\
                   STORY_TYPES, OLD_TYPES, NON_OPTIONAL_TYPES, CREDIT_TYPES
from .feature import (Feature, FeatureLogo, FeatureType, FeatureRelation,
                      FeatureRelationType)
from .cover import Cover
from .issuereprint import IssueReprint
from .reprint import Reprint
from .reprinttoissue import ReprintToIssue
from .reprintfromissue import ReprintFromIssue
from .seriesbond import SeriesBondType, SeriesBond, BOND_TRACKING, \
                        SUBNUMBER_TRACKING, MERGE_TRACKING
from .image import ImageType, Image
from .creator import CreatorArtInfluence, Creator, CreatorDegree, \
                    CreatorNameDetail, CreatorSchool,\
                    Degree, CreatorMembership, CreatorRelation, NameType, \
                    CreatorNonComicWork, NonComicWorkType, NonComicWorkRole, \
                    NonComicWorkYear, RelationType, School, MembershipType
from .award import Award, ReceivedAward
from .datasource import DataSource, SourceType


def _display_uncertain(value, flag):
    return '%s?' % value if flag else value
