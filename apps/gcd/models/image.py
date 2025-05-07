import os

from django.db import models
from django.conf import settings
from django.contrib.contenttypes import models as content_models
from django.contrib.contenttypes.fields import GenericForeignKey
import django.urls as urlresolvers

from imagekit import ImageSpec, register
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFit, ResizeToFill
from imagekit.utils import get_field_info

from cv2 import FaceDetectorYN_create, cvtColor, resize, \
                COLOR_BGR2RGB, COLOR_RGB2BGR, INTER_CUBIC
from apps.oi import states

import numpy as np
from PIL import Image as pyImage


def convert_from_cv2_to_image(img: np.ndarray) -> pyImage:
    return pyImage.fromarray(cvtColor(img, COLOR_BGR2RGB))


def convert_from_image_to_cv2(img: pyImage) -> np.ndarray:
    return cvtColor(np.array(img), COLOR_RGB2BGR)


class CreatorCropToFace(ImageSpec):
    @property
    def processors(self):
        model, field_name = get_field_info(self.source)
        if model.type.id == 4:
            return [CropToFace()]
        else:
            return None


register.generator('creator:portrait_face', CreatorCropToFace)


class CropToFace(object):
    def process(self, image):
        image = convert_from_image_to_cv2(image)
        while image.shape[0] > 2000 or image.shape[1] > 2000:
            size = (int(image.shape[1]/2), int(image.shape[0]/2))
            image = resize(image, size, interpolation=INTER_CUBIC)
        model_location = \
            settings.STATICFILES_DIRS[0] + '/face_detection_yunet_2023mar.onnx'
        yunet = FaceDetectorYN_create(model_location, "",
                                      (300, 300), score_threshold=0.5)
        yunet.setInputSize((image.shape[1], image.shape[0]))
        _, faces = yunet.detect(image)  # faces: None, or nx15 np.array
        if faces is not None:
            x, y, w, h = faces[0][0:4].astype(int)
            if w < h:
                diff = h - w
                x -= diff//2
                if x < 0:
                    x = 0
                if x + h > image.shape[1]:
                    h = image.shape[1] - x
                w = h
            elif w > h:
                diff = w - h
                y -= diff//2
                if y < 0:
                    y = 0
                if y + w > image.shape[0]:
                    w = image.shape[0] - y
                h = w
            border = min(x, y, int(w*.2))
            if x+w+border > image.shape[1]:
                border = max(0, image.shape[1]-x-w)
            if y+h+border > image.shape[0]:
                border = max(0, image.shape[0]-y-h)
            faces = image[y-border:y + h+border, x-border:x + w+border]
            if w + 2*border > 50:
                faces = convert_from_cv2_to_image(faces)
                # for some reason, some images are not fully processed
                # on beta (production likely), but the avatar is shown
                # instead. If we do resize directly here, it works.
                resized = faces.resize((150, 150), pyImage.LANCZOS)
                return resized
        return pyImage.open(settings.STATICFILES_DIRS[0] + '/img/avatar.png')


class ImageType(models.Model):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_image_type'

    name = models.CharField(max_length=50, db_index=True, unique=True)
    unique = models.BooleanField(default=True)
    description = models.CharField(max_length=255)

    def __str__(self):
        return self.name


# we need to save the model instance first without a file to get an id and
# then save the file
def get_generic_image_path(instance, filename):
    return os.path.join(settings.GENERIC_IMAGE_DIR,
                        str(int(instance.id/1000)), filename)


class Image(models.Model):
    class Meta:
        app_label = 'gcd'
        db_table = 'gcd_image'

    content_type = models.ForeignKey(content_models.ContentType,
                                     on_delete=models.CASCADE, null=True)
    object_id = models.PositiveIntegerField(db_index=True, null=True)
    object = GenericForeignKey('content_type', 'object_id')

    type = models.ForeignKey(ImageType, on_delete=models.CASCADE)

    image_file = models.ImageField(upload_to=get_generic_image_path)
    scaled_image = ImageSpecField([ResizeToFit(width=400, upscale=False),],
                                  source='image_file',
                                  format='JPEG',
                                  options={'quality': 90})
    thumbnail = ImageSpecField([ResizeToFit(height=50, upscale=False),],
                               source='image_file', format='JPEG',
                               options={'quality': 90})
    icon = ImageSpecField([ResizeToFit(height=30, upscale=False),],
                          source='image_file',
                          format='JPEG', options={'quality': 90})
    cropped_face = ImageSpecField(id='creator:portrait_face',
                                  source='image_file',
                                  format='JPEG',
                                  options={'quality': 90})
    face_portrait = ImageSpecField([ResizeToFill(150, 150), ],
                                   source='cropped_face',
                                   format='JPEG',
                                   options={'quality': 90})
    marked = models.BooleanField(default=False)

    # Fields related to change management.
    created = models.DateTimeField(auto_now_add=True, null=True)
    modified = models.DateTimeField(auto_now=True, null=True)

    reserved = models.BooleanField(default=False, db_index=True)
    deleted = models.BooleanField(default=False, db_index=True)

    def delete(self):
        self.deleted = True
        self.reserved = False
        self.save()

    def deletable(self):
        return self.revisions.filter(changeset__state__in=states.ACTIVE)\
                             .count() == 0

    def description(self):
        return '%s for %s' % (self.type.description, str(self.object))

    def get_absolute_url(self):
        if self.content_type == content_models.ContentType.objects\
                                              .get(model='Issue'):
            return urlresolvers.reverse(
                'issue_images',
                kwargs={'issue_id': self.object.id})
        elif self.content_type == content_models.ContentType.objects\
                                                .get(model='Brand'):
            return urlresolvers.reverse(
                'show_brand',
                kwargs={'brand_id': self.object.id})

        elif self.content_type == content_models.ContentType.objects\
                                                .get(model='Creator'):
            return urlresolvers.reverse(
                'show_creator',
                kwargs={'creator_id': self.object.id})
        else:
            return ''

    def approved_changesets(self):
        from apps.oi.models import Changeset
        revision_ids = self.revisions.values_list('changeset__id', flat=True)
        return Changeset.objects.filter(id__in=revision_ids, state=5)\
                                .order_by('-modified')

    def __str__(self):
        return '%s: %s' % (str(self.object),
                           self.type.description.capitalize())
