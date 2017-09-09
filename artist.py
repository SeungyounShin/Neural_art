import ssl
ssl._create_default_https_context = ssl._create_unverified_context

from keras import backend
from keras.models import Model
from keras.applications.vgg16 import VGG16

from keras.preprocessing.image import ImageDataGenerator, array_to_img, img_to_array, load_img
import tensorflow as tf
import numpy as np
from PIL import Image

height = 512
width = 512
ordirany_img_shape = (0,0,0)

content_weight = 0.05
style_weight = 10
total_variation_weight = 2

loss = backend.variable(0.)

def jpg2arr(path):
  img = load_img(path)
  img = img_to_array(img)
  shape = img.shape
  ordirany_img_shape = shape
  img = img.reshape((1,) + shape)
  x = tf.image.resize_images(
      img,
      [height,width],
      method=tf.image.ResizeMethod.BILINEAR,
      align_corners=False
  )
  y = tf.Session().run(x)
  return y

def data_process(data):
    data[:, :, :, 0] -= 103.939
    data[:, :, :, 1] -= 116.779
    data[:, :, :, 2] -= 123.68
    data = data[:, :, :, ::-1]
    return backend.variable(data)

def content_loss(content, combination):
    return backend.sum(backend.square(combination - content))

def gram_matrix(x):
    features = backend.batch_flatten(backend.permute_dimensions(x, (2, 0, 1)))
    gram = backend.dot(features, backend.transpose(features))
    return gram

def style_loss(style, combination):
    S = gram_matrix(style)
    C = gram_matrix(combination)
    channels = 3
    size = height * width
    return backend.sum(backend.square(S - C)) / (4. * (channels ** 2) * (size ** 2))

def total_variation_loss(x):
    a = backend.square(x[:, :height-1, :width-1, :] - x[:, 1:, :width-1, :])
    b = backend.square(x[:, :height-1, :width-1, :] - x[:, :height-1, 1:, :])
    return backend.sum(backend.pow(a + b, 1.25))

content_image_path = './content.jpg'
style_image_path = './style.jpg'

content_array = jpg2arr(content_image_path)
style_array = jpg2arr(style_image_path)

content_image = data_process(content_array)
style_image = data_process(style_array)
combination_image = backend.placeholder((1, height, width, 3))

input_tensor = backend.concatenate([content_image,style_image,combination_image], axis=0)

model = VGG16(input_tensor=input_tensor, weights='imagenet',include_top=False)
layers = dict([(layer.name, layer.output) for layer in model.layers])

layer_features = layers['block2_conv2']
content_image_features = layer_features[0, :, :, :]
combination_features = layer_features[2, :, :, :]

loss += content_weight * content_loss(content_image_features,combination_features)

feature_layers = ['block1_conv2', 'block2_conv2',
                  'block3_conv3', 'block4_conv3',
                  'block5_conv3']
for layer_name in feature_layers:
    layer_features = layers[layer_name]
    style_features = layer_features[1, :, :, :]
    combination_features = layer_features[2, :, :, :]
    sl = style_loss(style_features, combination_features)
    loss += (style_weight / len(feature_layers)) * sl

loss += total_variation_weight * total_variation_loss(combination_image)

grads = backend.gradients(loss, combination_image)

outputs = [loss]
outputs += grads
f_outputs = backend.function([combination_image], outputs)

def eval_loss_and_grads(x):
    x = x.reshape((1, height, width, 3))
    outs = f_outputs([x])
    loss_value = outs[0]
    grad_values = outs[1].flatten().astype('float64')
    return loss_value, grad_values

class Evaluator(object):

    def __init__(self):
        self.loss_value = None
        self.grads_values = None

    def loss(self, x):
        assert self.loss_value is None
        loss_value, grad_values = eval_loss_and_grads(x)
        self.loss_value = loss_value
        self.grad_values = grad_values
        return self.loss_value

    def grads(self, x):
        assert self.loss_value is not None
        grad_values = np.copy(self.grad_values)
        self.loss_value = None
        self.grad_values = None
        return grad_values

evaluator = Evaluator()

x = np.random.uniform(0, 255, (1, height, width, 3)) - 128.

iterations = 10

import time
from scipy.optimize import fmin_l_bfgs_b

def image_return(x):
    x = x.reshape((height, width, 3))
    x = x[:, :, ::-1]
    x[:, :, 0] += 103.939
    x[:, :, 1] += 116.779
    x[:, :, 2] += 123.68
    x = np.clip(x, 0, 255).astype('uint8')
    return Image.fromarray(x)

for i in range(iterations):
    print('Start of iteration', i)
    start_time = time.time()
    x, min_val, info = fmin_l_bfgs_b(evaluator.loss, x.flatten(),
                                     fprime=evaluator.grads, maxfun=20)
    print('Current loss value:', min_val)
    end_time = time.time()
    print('Iteration %d completed in %ds' % (i, end_time - start_time))
    tmp_img = image_return(x)
    tmp_img.save("x"+str(i)+".jpg")

x = x.reshape((height, width, 3))
x = x[:, :, ::-1]
x[:, :, 0] += 103.939
x[:, :, 1] += 116.779
x[:, :, 2] += 123.68
x = np.clip(x, 0, 255).astype('uint8')
"""
x = tf.image.resize_images(
    x,
    [ordirany_img_shape[0],ordirany_img_shape[1]],
    method=tf.image.ResizeMethod.BILINEAR,
    align_corners=False
)
"""
result = Image.fromarray(x)
result.save("result.jpg")
print("FINISHED")
