
###############################################################
## IMPORTS
###############################################################

from imports import *

#-----------------------------------
def get_training_dataset():
  return get_batched_dataset(training_filenames)

#-----------------------------------
def get_validation_dataset():
  return get_batched_dataset(validation_filenames)

def get_validation_eval_dataset():
  return get_eval_dataset(validation_filenames)

#-----------------------------------
def get_aug_datasets():

    data_augmentation = tf.keras.Sequential([
      tf.keras.layers.experimental.preprocessing.RandomFlip('horizontal'),
      tf.keras.layers.experimental.preprocessing.RandomRotation(0.01),
      tf.keras.layers.experimental.preprocessing.RandomTranslation(0.1,0.1),
      tf.keras.layers.experimental.preprocessing.RandomContrast(0.1)
    ])

    augmented_train_ds = get_training_dataset().map(
      lambda x, y: (data_augmentation(x, training=True), y))

    augmented_val_ds = get_validation_dataset().map(
      lambda x, y: (data_augmentation(x, training=True), y))
    return augmented_train_ds, augmented_val_ds


###############################################################
## VARIABLES
###############################################################

data_path= os.getcwd()+os.sep+"data/tamucc/subset_3class/400"

sample_data_path= os.getcwd()+os.sep+"data/tamucc/subset_3class/sample"

CLASSES = [b'marsh', b'dev', b'other']

#smaller learning rate because fine tuning

#largeer patience
patience = 30

filepath = os.getcwd()+os.sep+'results/tamucc_subset_3class_mv2_best_weights_model3.h5'
weights_to_load = os.getcwd()+os.sep+'results/tamucc_subset_3class_mv2_best_weights_model2.h5'

train_hist_fig = os.getcwd()+os.sep+'results/tamucc_sample_3class_mv2_model3.png'
cm_filename = os.getcwd()+os.sep+'results/tamucc_sample_3class_mv2_model3_cm_val.png'
sample_plot_name = os.getcwd()+os.sep+'results/tamucc_sample_3class_mv2_model3_est24samples.png'


###############################################################
## EXECUTION
###############################################################

#images already shuffled

filenames = sorted(tf.io.gfile.glob(data_path+os.sep+'*.tfrec'))

nb_images = ims_per_shard * len(filenames)
print(nb_images)

split = int(len(filenames) * VALIDATION_SPLIT)

training_filenames = filenames[split:]
validation_filenames = filenames[:split]

validation_steps = int(nb_images // len(filenames) * len(validation_filenames)) // BATCH_SIZE
steps_per_epoch = int(nb_images // len(filenames) * len(training_filenames)) // BATCH_SIZE

print(steps_per_epoch)
print(validation_steps)

## data augmentation is typically used
augmented_train_ds, augmented_val_ds = get_aug_datasets()

###########################################################
#### fine-tuning

### use smaller learning rate when fine tuning, and use more patience


lr_callback = tf.keras.callbacks.LearningRateScheduler(lambda epoch: lrfn(epoch), verbose=True)

rng = [i for i in range(MAX_EPOCHS)]
y = [lrfn(x) for x in rng]
plt.plot(rng, [lrfn(x) for x in rng])
# plt.show()
plt.savefig(os.getcwd()+os.sep+'results/learnratesched2.png', dpi=200, bbox_inches='tight')


### finet-tuned - load weights, then freeze lower layers

## use more dropout for regularization
dropout_rate =0.75
model3 = mobilenet_model(len(CLASSES), (TARGET_SIZE, TARGET_SIZE, 3), dropout_rate=dropout_rate)

model3.load_weights(weights_to_load)


print("Number of tunable layers in the base model: ", len(model3.layers))

# Fine-tune from this layer onwards
fine_tune_at = 80

# Freeze all the layers before the `fine_tune_at` layer
for layer in model3.layers[:fine_tune_at]:
  layer.trainable =  False

# check this: which layers are frozen?
for i,layer in enumerate(model3.layers):
    print('layer %i: %s' % (i, ['trainable' if layer.trainable else 'frozen'][0]))



model3.compile(optimizer=tf.keras.optimizers.Adam(), #1e-4),
          loss='sparse_categorical_crossentropy',
          metrics=['accuracy'])

earlystop = EarlyStopping(monitor="val_loss",
                              mode="min", patience=patience)

# set checkpoint file
model_checkpoint = ModelCheckpoint(filepath, monitor='val_loss',
                                verbose=0, save_best_only=True, mode='min',
                                save_weights_only = True)

callbacks = [model_checkpoint, earlystop, lr_callback]


do_train = False #True

if do_train:

    # much slower to train
    history = model3.fit(augmented_train_ds, steps_per_epoch=steps_per_epoch, epochs=MAX_EPOCHS,
                          validation_data=augmented_val_ds, validation_steps=validation_steps,
                          callbacks=callbacks) #, class_weight = class_weights)

    # Plot training history
    plot_history(history, train_hist_fig)
    plt.close('all')
    K.clear_session()

else:
    model3.load_weights(filepath)



##########################################################
### evaluate
loss, accuracy = model3.evaluate(get_validation_eval_dataset(), batch_size=BATCH_SIZE)
print('Test Mean Accuracy: ', round((accuracy)*100, 2),' %')

##80


##########################################################
### predict
sample_filenames = sorted(tf.io.gfile.glob(sample_data_path+os.sep+'*.jpg'))


plt.figure(figsize=(16,16))

for counter,f in enumerate(sample_filenames):
    image, im = file2tensor(f, 'mobilenet')
    plt.subplot(8,4,counter+1)
    name = sample_filenames[counter].split(os.sep)[-1].split('_')[0]
    plt.title(name, fontsize=10)
    plt.imshow(tf.cast(image, tf.uint8))
    plt.axis('off')

    scores = model3.predict(tf.expand_dims(im, 0) , batch_size=1)
    n = np.argmax(scores[0])
    est_name = CLASSES[n].decode()
    if name==est_name:
       plt.text(10,50,'prediction: %s' % est_name,
                color='k', fontsize=12,
                ha="center", va="center",
                bbox=dict(boxstyle="round",
                       ec=(.1, 1., .5),
                       fc=(.1, 1., .5),
                       ))
    else:
       plt.text(10,50,'prediction: %s' % est_name,
                color='k', fontsize=12,
                ha="center", va="center",
                bbox=dict(boxstyle="round",
                       ec=(1., 0.5, 0.1),
                       fc=(1., 0.8, 0.8),
                       ))

# plt.show()
plt.savefig(sample_plot_name,
            dpi=200, bbox_inches='tight')
plt.close('all')




## confusion matrix
val_ds = get_validation_eval_dataset()

labs, preds = get_label_pairs(val_ds, model3)

p_confmat(labs, preds, cm_filename, CLASSES)


#77%