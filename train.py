import matplotlib.pyplot as plt
import tensorflow as tf
import pathlib
import random
import os


# 读取所有图片，返回打乱后所有图片地址，图片所对应的标签，标签命名
def get_paths_labels(data_root):
    # 获取所有图片的地址，并转换为列表
    all_image_paths = list(data_root.glob('*/*'))
    # 将地址转换为字符串
    all_image_paths = [str(path) for path in all_image_paths]
    # 打乱地址顺序
    random.shuffle(all_image_paths)
    # 通过文件夹名字，获取所有标签的名字，存放于列表
    label_names = sorted(item.name for item in data_root.glob('*/') if item.is_dir())
    # 将标签名字与索引对应，存放于字典
    label_to_index = dict((name, index) for index, name in enumerate(label_names))
    # 新建一个标签列表，对应图片地址列表
    all_image_labels = [label_to_index[pathlib.Path(path).parent.name] for path in all_image_paths]
    # 返回打乱后所有图片地址，图片所对应的标签，标签命名
    return all_image_paths, all_image_labels, label_names


# 对图片进行标准化
def preprocess_image(image):
    # 原始图片转换为tensor类型
    image = tf.image.decode_jpeg(image, channels=3)
    # 修改尺寸
    image = tf.image.resize(image, [image_height, image_width])
    # 绝对色彩信息
    image /= 255.0
    # 返回标准图像
    return image


# 加载和预处理图片
def load_and_preprocess_image(path):
    # 读取原始图像
    image = tf.io.read_file(path)
    # 预处理图像
    return preprocess_image(image)


# 打包标准图像-标签数据集
def create_dataset(images, labels):
    # 打包图像地址数据集
    image_ds = tf.data.Dataset.from_tensor_slices(images)
    # 动态加载和标准化图片，应对大数据
    image_ds = image_ds.map(load_and_preprocess_image, num_parallel_calls=AUTOTUNE)
    # 打包标签数据集
    label_ds = tf.data.Dataset.from_tensor_slices(labels)
    # 打包标准图像-标签数据集
    image_label_ds = tf.data.Dataset.zip((image_ds, label_ds))
    # 返回标准图像-标签数据集
    return image_label_ds


# 数据根目录
data_root = pathlib.Path("./flower_photos")
# 裁剪的图片尺寸，高度，宽度
image_height, image_width = 192, 192
# 动态调整CPU
AUTOTUNE = tf.data.experimental.AUTOTUNE

# 读取所有图片，返回打乱后所有图片地址，图片所对应的标签，标签命名
all_image_paths, all_image_labels, label_names = get_paths_labels(data_root)
# 打包标准图像-标签数据集
image_label_ds = create_dataset(all_image_paths, all_image_labels)

# 图片总数
images_count = len(all_image_paths)
# 分批大小
batch_size = 32

# 训练数据集为前80%
train_ds = image_label_ds.take(tf.cast(images_count * 0.8, "int64"))
# 验证数据集为后20%
val_ds = image_label_ds.skip(tf.cast(images_count * 0.8, "int64"))
# 打乱训练集
train_ds = train_ds.shuffle(buffer_size=tf.cast(images_count * 0.8, "int64"))
# 打乱验证集
val_ds = val_ds.shuffle(buffer_size=tf.cast(images_count * 0.2, "int64"))
# 重复训练集
train_ds = train_ds.repeat()
# 重复验证集
val_ds = val_ds.repeat()
# 训练集分批
train_ds = train_ds.batch(batch_size=batch_size)
# 验证集分批
val_ds = val_ds.batch(batch_size=batch_size)

# 获取已存在的MobileNetV2模型
mobile_net = tf.keras.applications.MobileNetV2(input_shape=(image_height, image_width, 3), include_top=False)
# MobileNet的权重为不可训练
mobile_net.trainable = False
# 模型层次：mobile_net，平均池，全连接
model = tf.keras.Sequential([
    mobile_net,
    tf.keras.layers.GlobalAveragePooling2D(),
    tf.keras.layers.Dense(len(label_names), activation='softmax')])
# 模型编译
model.compile(optimizer=tf.keras.optimizers.Adam(), loss='sparse_categorical_crossentropy', metrics=["accuracy"])
# 模型信息概览
model.summary()
# 生成模型图片
tf.keras.utils.plot_model(model, to_file='model.png', show_shapes=True)
# 模型存储位置
checkpoint_save_path = "./plant.ckpt"
# 判断是否已有模型参数
if os.path.exists(checkpoint_save_path + '.index'):
    print('-------------load the model-----------------')
    # 加载现有模型参数
    model.load_weights(checkpoint_save_path)
# 设置回调函数，每迭代一次存储最优模型参数
cp_callback = tf.keras.callbacks.ModelCheckpoint(filepath=checkpoint_save_path, save_weights_only=True,
                                                 save_best_only=True)
# 保证对每次迭代对所有图片都进行训练，images_count = steps_per_epoch * batch_size
steps_per_epoch = tf.math.ceil(images_count / batch_size).numpy()
# 拟合，训练数据集train_ds，迭代3次，每次迭代批数steps_per_epoch，验证数据集val_ds，回调函数存储每次迭代最优解
history = model.fit(train_ds, epochs=3, steps_per_epoch=steps_per_epoch, validation_data=val_ds, validation_steps=5,
                    callbacks=[cp_callback])

# 训练集命中
acc = history.history['accuracy']
# 验证集命中
val_acc = history.history['val_accuracy']
# 训练集损失函数
loss = history.history['loss']
# 验证集损失函数
val_loss = history.history['val_loss']

plt.subplot(1, 2, 1)
plt.plot(acc, label='Training Accuracy')
plt.plot(val_acc, label='Validation Accuracy')
plt.title('Training and Validation Accuracy')
plt.legend()

plt.subplot(1, 2, 2)
plt.plot(loss, label='Training Loss')
plt.plot(val_loss, label='Validation Loss')
plt.title('Training and Validation Loss')
plt.legend()
plt.show()
