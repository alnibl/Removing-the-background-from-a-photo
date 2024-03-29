# -*- coding: utf-8 -*-
"""Background removal.ipynb"

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1J-MThO9YaKcxexHo6ir4r3Scor3nXzbj

## Описание

В ноутбуке реализован один из нейросетевых методов удаления фона на изображении.

Нейронная сеть представляет собой модель u-net в сочетании с предобученной сетью EfficientNetV2M. u-net имеет две ветви уменьшения изображени до латентного пространства и две ветви увеличения изображения. Каждая ветвь u-net имеет разные ядра свертки. Ветвь сети EfficientNetV2M была заморожена и используется для получения фичь от изображения.

На вход опступает изображение машины на фоне (лес, природа, поле). На выход сеть выдает изображение машины на черном фоне.

Входное изображение обрабатывается двумя ветвями u-net и отдельно ветьвью EfficientNetV2M.Происходит постепенно уменьшение изображения до латентного пространства, затем полученные признаки от двух сетей конкатенируются и постепенно восстанавливаются в исходный размер изображения. В данном случае сеть была обучана на изображениях размеров 256, 384, 3.

Общее количество фото фонов для обучения нейронной сети - 2528 изображений.
Из них:
- получены путем парсинга сайта https://oir.mobi – 1420 шт.
- взяты фреймы из видео YouTube – 406 шт.
- фото из баз в интернете(частично использованы базы DeepLoc, DeepLocCross, Freiburg Street Crossing, FRIDA ) - 702 шт.

Автомобили.
Общее количество фото - 2528 штук. Фото парсились с сайта http://www.motorpage.ru.
"""

gpu_info = !nvidia-smi
gpu_info = '\n'.join(gpu_info)
if gpu_info.find('failed') >= 0:
  print('Not connected to a GPU')
else:
  print(gpu_info)

# для lbumentations (аугментация изображений и ключевых точек)
!pip install -U albumentations --no-binary qudida,albumentations
!pip install -U git+https://github.com/albumentations-team/albumentations

# установка библиотек
from keras.models import Model, Sequential 
from keras.layers import Dense, Flatten, Reshape, Input, Conv2DTranspose, concatenate
from keras.layers import Activation, MaxPooling2D, MaxPooling1D, Conv2D, BatchNormalization
from keras.layers import Concatenate, Dropout, SpatialDropout1D, Embedding, Conv1D
from keras.layers import  LSTM, LeakyReLU, UpSampling2D
from tensorflow.keras.optimizers import Adam 
from tensorflow.keras.applications import vgg19, EfficientNetV2M
from keras.preprocessing import image 
from tensorflow.keras.utils import load_img, img_to_array
from tensorflow.keras.utils import plot_model
from keras import utils 
from PIL import Image 
from sklearn.model_selection import train_test_split 
from sklearn.preprocessing import StandardScaler, MinMaxScaler 
import numpy as np 
import pandas as pd 
import matplotlib.pyplot as plt 
from keras import backend as K 
import os 
import time
import random
import shutil
import sys
from tqdm import tqdm
import albumentations as A
import cv2
from keras.models import load_model

from tensorflow.python.platform.tf_logging import set_verbosity, FATAL

# отключаю отображение некритических предупреждений
set_verbosity(FATAL)
os.environ["TF_CPP_MIN_LOG_LEVEL"] = '0'

# подключаю гугл диск
from google.colab import drive
drive.mount('/content/drive')

"""## Разделение базы"""

# пути к файлам на google  диске
way_car = '/content/drive/MyDrive/Базы/Обрезанные/Для аугментации'
way_background = '/content/drive/MyDrive/Базы/Фон'

# создаю папки в colab
!mkdir Автомобили
!mkdir Фон

# Копирую файлы с авто в одну папку
for i in sorted(os.listdir(way_car)):
  car_ = way_car + '/' + i + '/'
  for im in sorted(os.listdir(car_)):
    shutil.copy(car_ + im, '/content/Автомобили/' + i + im) 
# собираю имена файлов
car_name = sorted(os.listdir('/content/Автомобили/'))
print(f'Количество авто в папке: {len(car_name)}')

# Копирую файлы с фоном в одну папку
for i in sorted(os.listdir(way_background)):
  background_ = way_background + '/' + i + '/'
  for im in sorted(os.listdir(background_)):
    shutil.copy(background_ + im, '/content/Фон/' + i + im) 
# собираю имена файлов
background_name = sorted(os.listdir('/content/Фон/'))
print(f'Количество фонов в папке: {len(background_name)}')

"""Так как задача спецефическая и Y я планирую генерировать на ходу, то разделение выборки сделаю только по X.

В xtrain, ytrain, xtest, ytest, xval, yval будут имена файлов, а не сами файлы
"""

# переведу в numpy
car_name = np.array(car_name)
background_name = np.array(background_name)

# для разделения на выборки использую train_test_splite библиотека sklearn
# возму 5% на тестовую выборку
# shuffle=True - перемешиваю, фиксирую seed -> random_state=11
# для машин
X_train_car, X_test_car = train_test_split(car_name, test_size=0.05, shuffle=True, random_state=11) 
print(X_train_car.shape, X_test_car.shape)

# для фонов
X_train_bac, X_test_bac = train_test_split(background_name, test_size=0.05, shuffle=True, random_state=11) 
print(X_train_bac.shape, X_test_bac.shape)

# для проверчной возьму 10 %
X_Train_Car, X_Val_Car, = train_test_split(X_train_car, test_size=0.10, shuffle=True, random_state=11)
print(X_Train_Car.shape, X_Val_Car.shape)

X_Train_Bac, X_Val_Bac, = train_test_split(X_train_bac, test_size=0.10, shuffle=True, random_state=11)
print(X_Train_Bac.shape, X_Val_Bac.shape)

# сохраняю на диск
np.save('/content/drive/MyDrive/Тестовые задания/МАЙНДСЭТ/X_Train_Car.npy', X_Train_Car)
np.save('/content/drive/MyDrive/Тестовые задания/МАЙНДСЭТ/X_Val_Car.npy', X_Val_Car)
np.save('/content/drive/MyDrive/Тестовые задания/МАЙНДСЭТ/X_test_car.npy', X_test_car)

np.save('/content/drive/MyDrive/Тестовые задания/МАЙНДСЭТ/X_Train_Bac.npy', X_Train_Bac)
np.save('/content/drive/MyDrive/Тестовые задания/МАЙНДСЭТ/X_Val_Bac.npy', X_Val_Bac)
np.save('/content/drive/MyDrive/Тестовые задания/МАЙНДСЭТ/X_test_bac.npy', X_test_bac)

"""## Нейронная сеть, функции, код"""

img_shape = (256, 384, 3)

def model_EfficientNetV2M():
  
  EfNetV2M_in = Input(img_shape)
  #скачиваю архитектуру и веса 
  EfNetV2M = EfficientNetV2M(include_top=False, weights="imagenet", 
                                    input_shape=img_shape, input_tensor=EfNetV2M_in,
                                    include_preprocessing=False)
  #получаю последний сверточный слой
  EfNetV2M_out = EfNetV2M.get_layer('top_activation').output
  # далее добавляю свой слой
  x = MaxPooling2D(4) (EfNetV2M_out) 

  EfNetV2M_model = Model(EfNetV2M_in, x, name='model_EfficientNetV2M')
  EfNetV2M_model.trainable = False # веса замораживаю

  return EfNetV2M_model

EfNetV2M_model = model_EfficientNetV2M()

for i, layer in enumerate(EfNetV2M_model.layers):
  print(i, layer.name)

EfNetV2M_model.summary()

# вся сеть
img_shape = (256, 384, 3)  # размер изображения
height = img_shape[0]
width = img_shape[1]


def generator(EfNetV2M_model):
    '''
        EfNetV2M_model - модель с замороженными весами, помогающая собирать фичи от входного изображения
    '''
    filters = 32  # минимальное число фильтров

    def en_conv2d(layer_input, filters, k_size_1=4, k_size_2=4, strides=2, bn=True,
                  maxp=False):  # слой с понижением разрешения.
        '''
        layer_input - слой на вход.
        filters- количество фильтров
        k_size_1 - размер ядра свертки
        k_size_2 - размер ядра свертки
        strides - какой strides применять в слое Conv2D
        bn - BatchNormalization
        maxp - MaxPooling2D
        '''
        en = Conv2D(filters, kernel_size=k_size_1, strides=1, padding='same')(layer_input)
        en = LeakyReLU(alpha=0.2)(en)
        en = Conv2D(filters, kernel_size=k_size_2, strides=strides, padding='same')(en)
        en = LeakyReLU(alpha=0.2)(en)
        if bn:
            en = BatchNormalization(momentum=0.8)(en)
            if maxp:
                en = MaxPooling2D(2)(en)
        return en

        # слой с повышением разрешения
    def de_conv2d(layer_input, skip_input, filters, k_size_1=4, k_size_2=4, dropout_rate=0):
        '''
        layer_input - слой на вход
        skip_input -  предыдущий слой от слоя с понижением разрешения (conv2d)
        filters - количество фильтров
        k_size_1 - размер ядра свертки
        k_size_2 - размер ядра свертки
        dropout_rate - применять ли dropout
        '''
        # увеличивам разрешение в 2 раза
        de = UpSampling2D(size=2)(layer_input)
        # strides=1, padding='same',  поэтому разрешение сохраняется
        de = Conv2D(filters, kernel_size=k_size_2, strides=1, padding='same', activation='relu')(de)
        # strides=1, padding='same',  поэтому разрешение сохраняется
        de = Conv2D(filters, kernel_size=k_size_1, strides=1, padding='same', activation='relu')(de)
        if dropout_rate:
            de = Dropout(dropout_rate)(de)
        de = BatchNormalization(momentum=0.8)(de)
        # соединяем skip-слой от conv2d (слой с понижением разрешения) и слой от deconv2d (слой с повышением разрешения)
        de = Concatenate()([de, skip_input])
        return de

    e0 = Input(shape=img_shape, name="condition")  # входное изображение (условие)
    
    # получаю фичи от входного изображения (с машиной) c помощью предобученной сети EfficientNetV2M
    cars_features = EfNetV2M_model(e0)  # модель EfficientNetV2M используется как слой (на вход подаю входное изображение)

    # Ветка 1, где понижается разрешение
    e1 = en_conv2d(e0, filters, bn=False)
    e2 = en_conv2d(e1, filters * 2)
    e3 = en_conv2d(e2, filters * 4)  # чем меньше размер карт активаций
    e4 = en_conv2d(e3, filters * 8)  # тем больше должно быть фильтров в сверточном слое
    e5 = en_conv2d(e4, filters * 8)
    e6 = en_conv2d(e5, filters * 8)
    e7 = en_conv2d(e6, filters * 8)

    # Ветка 2, где понижается разрешение
    ee1 = en_conv2d(e0, filters, k_size_1=2, k_size_2=2, bn=False)
    ee2 = en_conv2d(ee1, filters * 2, k_size_1=2, k_size_2=2, strides=1, maxp=True)
    ee3 = en_conv2d(ee2, filters * 4, k_size_1=2, k_size_2=2, strides=1, maxp=True)  # чем меньше размер карт активаций
    ee4 = en_conv2d(ee3, filters * 8, k_size_1=2, k_size_2=2, strides=1, maxp=True)  # тем больше должно быть фильтров в сверточном слое
    ee5 = en_conv2d(ee4, filters * 8, k_size_1=2, k_size_2=2, strides=1, maxp=True)
    ee6 = en_conv2d(ee5, filters * 8, k_size_1=2, k_size_2=2, strides=1, maxp=True)
    ee7 = en_conv2d(ee6, filters * 8, k_size_1=2, k_size_2=2, strides=1, maxp=True)

    e_cont = Concatenate()([e7, ee7, cars_features])  # соединяю 3 слоя вместе (от ветки 1 и ветки 2 и от модели EfNetV2M)
    e_cont = Conv2D(filters * 8, kernel_size=4, strides=1, padding='same', activation='relu', name='d_cont')(
        e_cont)  # прохожусь ещё раз сверткой

    # Ветка 1 повышения разрешения
    d1 = de_conv2d(e_cont, e6, filters * 8)
    d2 = de_conv2d(d1, e5, filters * 8)
    d3 = de_conv2d(d2, e4, filters * 8)  # чем больше размер карт активаций
    d4 = de_conv2d(d3, e3, filters * 4)  # тем меньше должно быть фильтров в сверточном слое
    d5 = de_conv2d(d4, e2, filters * 2)
    d6 = de_conv2d(d5, e1, filters)

    # Ветка 2 повышения разрешения
    dd1 = de_conv2d(e_cont, ee6, filters * 8, k_size_1=2, k_size_2=2)
    dd2 = de_conv2d(dd1, ee5, filters * 8, k_size_1=2, k_size_2=2)
    dd3 = de_conv2d(dd2, ee4, filters * 8, k_size_1=2, k_size_2=2)  # чем больше размер карт активаций
    dd4 = de_conv2d(dd3, ee3, filters * 4, k_size_1=2, k_size_2=2)  # тем меньше должно быть фильтров в сверточном слое
    dd5 = de_conv2d(dd4, ee2, filters * 2, k_size_1=2, k_size_2=2)
    dd6 = de_conv2d(dd5, ee1, filters, k_size_1=2, k_size_2=2)

    # для ветки 1 - UpSampling2D
    d7 = UpSampling2D(size=2)(d6)
    # и Conv2D
    output_img_1 = Conv2D(3, kernel_size=4, strides=1, padding='same', activation='tanh', name='output_img_1')(d7)
    # для ветки 2 - Conv2DTranspose
    output_img_2 = Conv2DTranspose(3, kernel_size=2, strides=2, padding='same', activation='tanh', name='output_img_2')(dd6)
    # соединяю вместе
    output_img_cont = Concatenate(name='output_img_cont')([output_img_1, output_img_2])
    # прохожусь и Conv2D, интенсивность должна быть от -1 до 1, поэтому tanh
    output = Conv2D(3, kernel_size=4, strides=1, padding='same', activation='tanh', name='Gen_output')(output_img_cont)

    return Model(e0, output, name="Generator")

model = generator(EfNetV2M_model)
model.summary()

# посмотрим архитектуру сети на картинке
plot_model(model, show_shapes=True)

"""Аугментацию изображений буду проводить с помощью библиотеки Albumentations"""

# Albumentations
# задаю трансформацию для авто
car_transform = A.Compose([A.HorizontalFlip(p=0.5), # горизонтальное отражение
                       A.Rotate(limit=70, interpolation=1, border_mode=4, value=None,
                       mask_value=None, always_apply=False, p=0.5)]) # поворот

# трансформация для фона
# случайно кропаю часть картинки размером 256 на 384
back_transform = A.Compose([A.RandomCrop(256, 384, always_apply=True, p=1),
                            A.HorizontalFlip(p=0.5),    # горизонтальное отражение
                            A.HueSaturationValue(p=0.5),# насыщенность                                         
                            A.RGBShift(p=0.5),          # изменение RGB            
                            A.RandomBrightnessContrast(p=0.5), # контрастность
                            A.Rotate(limit=90, interpolation=1, border_mode=4, 
                                     value=None, mask_value=None, always_apply=False, p=0.5), # поворот
                            A.RandomFog(fog_coef_lower=0.4, fog_coef_upper=0.5, alpha_coef=0.1, p=0.5)]) # эффект тумана

# функция формирования данных в батч во время обучения НС
img_width = 384
img_height = 256
batch_size = 8
path_car = '/content/Автомобили/'
path_background = '/content/Фон/'

def x_train_training_data(batch_size, X_car, X_background, path_car, path_background):
    x_tr = []
    y_tr = []

    # Размеры фото авто, которую буду налаживать на фон
    rcs = [(80, 60), (120, 90), (160, 120), (200, 150), (240, 180),(280, 210)] 

    for i in range(batch_size):
      car = Image.open(os.path.join(path_car, X_car[i]))
      car_size = random.choice(rcs)  # Случайно выбираю размер resize, который буду применять к изображению машины
      car = car.resize(car_size)
      car_np = img_to_array(car).astype('uint8')
      car_np = car_transform(image=car_np)['image']
      
      background = Image.open(os.path.join(path_background, X_background[i])).convert('RGB') # открываю фон
      background_np = img_to_array(background).astype('uint8')
      background_np = back_transform(image=background_np)['image']  # Применяю трансформация для фона
      
      # координаты расположения авто на фоне, по оси х. Случайное число от 0 до 384 - car_size[1]
      x = random.randint(0, img_width - car_size[0])
      # координаты расположения авто на фоне, по оси y. Случайное число от 0 до 256 - car_size[0]
      y = random.randint(0, img_height - car_size[1])
      
      background_result = Image.fromarray(background_np).convert('RGB')
      background_result.paste(car, (x, y), car)  # налаживаю машину на фон, координаты x и y
      background_result = np.array(background_result) # это готовый X для нейрости
      

      zeors_array = np.zeros((256, 384, 3)).astype('uint8') 
      car_result = Image.fromarray(zeors_array).convert('RGB')
      car_result.paste(car, (x, y), car)  # налаживаю машину на черный фон, размером 256х384, координаты x и y
      car_result = np.array(car_result) # это готовый Y для нейрости

      x_tr.append(background_result)  # Добавляем очередной элемент в xTrain
      y_tr.append(car_result)  # Добавляем очередной элемент в yTrain

    x_tr = np.array(x_tr)  # Перевожу в numpy
    y_tr = np.array(y_tr)  # Перевожу в numpy

    return x_tr, y_tr

# функция для отображения
def visualize(image):
  #image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
  plt.figure(figsize=(10, 10))
  plt.axis('off')
  plt.imshow(image)

# для примера создам батч X и Y
x_tr, y_tr = x_train_training_data(batch_size, X_Train_Car, X_Train_Bac, path_car, path_background)

# размер батча данных (X и Y)
x_tr.shape, y_tr.shape

# посмотрим, как выглядит X и Y
fig, ax = plt.subplots(x_tr.shape[0], 2, figsize=(35, 45))
for i in range(x_tr.shape[0]):
    ax[i, 0].imshow(x_tr[i])
    ax[i, 1].imshow(y_tr[i])
    plt.show

# функция отображение результата в процессе обучения
# num_lin = количество строк для отображения

def imege_pred(model, x_tr, x_val, num_lin = 2):

    img_width = 384
    img_height = 256

        
    # делаю predict и обратно нормирую значения пикселей для x_tr
    pred_train = (model.predict(x_tr) + 1) * 127.5  
    # делаю predict и обратно нормирую значения пикселей для x_val
    pred_val = (model.predict(x_val) + 1) * 127.5
    # значения x_tr возвращаю в диапазон от 0 до 255
    x_tr = ((x_tr + 1)*127.5).astype('uint8')
        

    fig, ax = plt.subplots(num_lin, 3, figsize=(25, 16))  # создаем сетку с num_lin строкой и 3 столбцами

    for i in range(num_lin):

        # Случайное число от 0 до 8 (количество элементов в x_train)
        el = np.random.choice(x_tr.shape[0], replace=False)
                 
        # отображаю изображение авто на фоне       
        ax[i, 0].imshow(x_tr[el])
        ax[i, 0].set_title('До нейросети')

        # отображаю результат после нейросети на train
        ax[i, 1].imshow((pred_train[el].astype('uint8')))
        ax[i, 1].set_title('Train')

        # отображаю результат после нейросети на val
        ax[i, 2].imshow(pred_val[el].astype('uint8')) 
        ax[i, 2].set_title('Validation')

    plt.show()
    plt.close()  # Завершаем работу с plt

# проверяю работу функции отображения результата
# создам батч X и Y
x_tr, y_tr = x_train_training_data(batch_size, X_Train_Car, X_Train_Bac, path_car, path_background)
x_val, y_val = x_train_training_data(batch_size, X_Val_Car, X_Val_Bac, path_car, path_background)
x_tr = (x_tr/127.5) - 1
x_val = (x_val/127.5) -1

# отображаю
imege_pred(model, x_tr, x_val, 2)

# первый запуск, веса еще не подстроились под нащу задачу, поэтому изображения train и val мутные

"""Функция обучения нейронной сети"""

# функция обучения нейронной сети
batch_size = 8
epochs = 1

def train(model, epochs, batch_size):

  model_loss_list = [] # массив значений ошибки 
  test_loss_list = []  # массив значений ошибки для проверочной выборки

  for epoch in range(epochs):

    # перемешиваю индексы, чтобы в каждой эпохе обучения batch_size картинок был разным, случайным.
    inds_car = np.random.choice(X_Train_Car.shape[0], X_Train_Car.shape[0], replace=False) # получаю индексы, replace=False - индексы без повторений.
    inds_bac = np.random.choice(X_Train_Bac.shape[0], X_Train_Car.shape[0], replace=False)

    for batch in tqdm(range(X_Train_Car.shape[0]//batch_size)): # эпоха (X_Train.shape[0]) делится на батчи, длина цикла - количество альтераций с batch_size
      
      idx_batch_car = inds_car[batch*batch_size:(batch+1)*batch_size] # в каждой альтерации цикла получаю индексы для одного batch'а
      idx_batch_bac = inds_bac[batch*batch_size:(batch+1)*batch_size]
      inds_val_car = np.random.choice(X_Val_Car.shape[0], batch_size, replace=False) # случайные индексы (размером batch_size) для проверочной выборки
      inds_val_bac = np.random.choice(X_Val_Bac.shape[0], batch_size, replace=False)

      x_name_batch_car = X_Train_Car[idx_batch_car]   # получаю X (пока это просто имена фото)размером один batch_size.
      x_name_batch_bac = X_Train_Bac[idx_batch_bac]
      x_name_batch_val_car = X_Val_Car[inds_val_car]  # имена изображений из проверочной выборки количеством batch_size.
      x_name_batch_val_bac = X_Val_Bac[inds_val_bac] 

      X, Y = x_train_training_data(batch_size, x_name_batch_car, x_name_batch_bac, path_car, path_background)# функция возвращает  X, Y для подачи в нейросеть.
      x_val, y_val = x_train_training_data(batch_size, x_name_batch_val_car, x_name_batch_val_bac, path_car, path_background)

      X = (X/127.5) - 1                        # нормализую X в диапазон от -1 до 1
      Y = (Y/127.5) - 1 
      x_val = (x_val/127.5) - 1                        
      y_val = (y_val/127.5) - 1 

      model_loss = model.train_on_batch(X, Y)       # тренерую модель методом train_on_batch
      test_loss = model.test_on_batch(x_val, y_val) # получаю ошибку на проверочной выборке

      model_loss_list.append(model_loss)     # сохраняю значения ошибки модели
      test_loss_list.append(test_loss)       # сохраняю значения ошибки на проверочной выборки


      # отображаю результат с помощью функции imege_pred
      if batch == 0:
        imege_pred(model, X, x_val, 2)

      # вывожу значения ошибок
      if batch % 20 == 0:
        print(f'"Эпоха:"{epoch}, mse_train:{round(model_loss,4)}, mse_val:{round(test_loss,4)}')

      # # сохраняю модель
      if (batch % 134 == 0) and (batch != 0):
        # сохраняю модель
        model.save('/content/drive/MyDrive/Тестовые задания/МАЙНДСЭТ/model.h5')


  # Сохраняю модель
  model.save('/content/drive/MyDrive/Тестовые задания/МАЙНДСЭТ/model.h5')
  # отображаю результат
  imege_pred(model, X, x_val, 2)

  # графики ошибок
  plt.plot(model_loss_list, label='Ошибка на обучающей выборки')
  plt.legend()
  plt.show()
  plt.plot(test_loss_list, label='Ошибка на проверочной')
  plt.legend()
  plt.show()

"""## Обучаю"""

# загружаю имена файлов train и val
X_Train_Car = np.load('/content/drive/MyDrive/Тестовые задания/МАЙНДСЭТ/X_Train_Car.npy')
X_Val_Car = np.load('/content/drive/MyDrive/Тестовые задания/МАЙНДСЭТ/X_Val_Car.npy')
X_test_car = np.load('/content/drive/MyDrive/Тестовые задания/МАЙНДСЭТ/X_test_car.npy')


X_Train_Bac = np.load('/content/drive/MyDrive/Тестовые задания/МАЙНДСЭТ/X_Train_Bac.npy')
X_Val_Bac= np.load('/content/drive/MyDrive/Тестовые задания/МАЙНДСЭТ/X_Val_Bac.npy')
X_test_bac = np.load('/content/drive/MyDrive/Тестовые задания/МАЙНДСЭТ/X_test_bac.npy')

# создаю модель
#model = generator(EfNetV2M_model)

# Загружаю модель
model = load_model('/content/drive/MyDrive/Тестовые задания/МАЙНДСЭТ/model.h5')

# компилирую модель
model.compile(loss='mse', optimizer=Adam(learning_rate=0.001))

batch_size = 8
epochs = 10 
train(model, epochs, batch_size)

batch_size = 8
epochs = 10 
train(model, epochs, batch_size)

batch_size = 8
epochs = 20 
train(model, epochs, batch_size)

batch_size = 8
epochs = 20 
train(model, epochs, batch_size)

batch_size = 8
epochs = 50 
train(model, epochs, batch_size)

# Загружаю модель
model = load_model('/content/drive/MyDrive/Тестовые задания/МАЙНДСЭТ/model.h5')

# компилирую модель
model.compile(loss='mse', optimizer=Adam(learning_rate=0.001))

batch_size = 8
epochs = 30 
train(model, epochs, batch_size)

# Загружаю модель
model = load_model('/content/drive/MyDrive/Тестовые задания/МАЙНДСЭТ/model.h5')

# компилирую модель
model.compile(loss='mse', optimizer=Adam(learning_rate=0.0001))

batch_size = 8
epochs = 30 
train(model, epochs, batch_size)

batch_size = 8
epochs = 20 
train(model, epochs, batch_size)

"""## Проверка результата"""

# Загружаю модель
model = load_model('/content/drive/MyDrive/Тестовые задания/МАЙНДСЭТ/model.h5')

x_test, y_test = x_train_training_data(batch_size, X_test_car, X_test_bac, path_car, path_background)
x_test = (x_test/127.5) -1

# отображаю только на тестовом набре
imege_pred(model, x_test, x_test, 5)

# проверяю на картинках из интернета
# путь к изображению
path = '/content/'
car = ['Chevrolet_Fields_Poppies_490947.jpg','1615456981181593750.jpg', '2.jpg',
       '6.jpg','5.jpg','1df78au-960.jpg', '3.jpg', '4.jpg', '7.jpg','8.jpg', '397406_full.jpeg', '9.jpg']

for i in range(len(car)):
  # откываю
  im = Image.open(os.path.join(path, car[i])).convert('RGB')
  # меняю размер
  im = im.resize((384, 256)) 
  # перевожу в numpy, меняю тип
  im = img_to_array(im).astype('uint8')
  # нормализую в значения от -1 до 1
  im_ = (im/127.5) - 1
  # подаю в сеть, затем возвращаю значения в диапазон от 0 до 255
  pred = (model.predict(im_[None]) + 1) * 127.5

  fig, ax = plt.subplots(1, 2, figsize=(15, 14)) # отображаю 
  ax[0].imshow(im)
  ax[1].imshow(pred[0].astype('uint8'))
  plt.show()
