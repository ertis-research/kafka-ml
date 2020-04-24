
from django.test import TestCase
from automl.models import MLModel, Deployment, Configuration, TrainingResult
from rest_framework import status
import json
import os
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
import tensorflow as tf
from tensorflow import keras

ML_CODE = "model=tf.keras.Sequential([\n      tf.keras.layers.Flatten(input_shape=(28, 28)),\n      tf.keras.layers.Dense(128, activation=tf.nn.relu),\n      tf.keras.layers.Dense(10, activation=tf.nn.softmax)\n])\nmodel.compile(optimizer='adam',\n    loss='sparse_categorical_crossentropy',\n    metrics=['accuracy'])"
class ModelViewTest(TestCase):

    @classmethod
    def setUpTestData(self):
        self.number_of_models = 3
        self.code = ML_CODE

        for model in range(self.number_of_models):
            MLModel.objects.create(name='Model %s' % model, code = 'Code %s' % model)
           
    def test_url_all_models(self): 
        resp = self.client.get('/models/') 
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue( len(resp.data) == self.number_of_models)

    def test_delete(self):
        resp = self.client.delete('/models/1')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(MLModel.objects.all().count() == (self.number_of_models-1))

    def test_delete_fail(self):
        resp = self.client.delete('/models/'+str(self.number_of_models+1))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create(self):
        data={'name': 'Test model', 'code': self.code}
        resp = self.client.post('/models/', content_type= 'application/json', data = data)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        
        obj = MLModel.objects.latest('id')
        filepath = os.path.join(settings.MEDIA_ROOT, settings.MODELS_DIR)+str(obj.id)+'.h5'
        self.assertTrue(os.path.exists(filepath))

        resp = self.client.delete('/models/'+str(obj.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(os.path.exists(filepath))

    def test_create_fail(self):
        data={'name': 'Test model', 'code': 'fail_code'}
        resp = self.client.post('/models/', content_type= 'application/json', data = data)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update(self):
        data={'code': self.code, 'name': 'name'}
        resp = self.client.put('/models/'+str(self.number_of_models), content_type= 'application/json', data = data)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        filepath = os.path.join(settings.MEDIA_ROOT, settings.MODELS_DIR)+str(self.number_of_models)+'.h5'
        self.assertTrue(os.path.exists(filepath))

        resp = self.client.delete('/models/'+str(self.number_of_models))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(os.path.exists(filepath))


class ResultViewTest(TestCase):

    @classmethod
    def setUpTestData(self):
        model = MLModel.objects.create(name='Model', code = 'Code')
        configuration =  Configuration.objects.create(name='Configuration')
        configuration.ml_models.add(model)
        configuration.save()
        deployment = Deployment.objects.create(batch=1, configuration=configuration)
        result = TrainingResult.objects.create(deployment=deployment, model=model)
        self.resultID=result.pk
    
    def test_upload_results(self):
        string_model = """def create_model(): 
        model = tf.keras.models.Sequential([  
            keras.layers.Dense(512, activation='relu', input_shape=(784,)), 
            keras.layers.Dropout(0.2), 
            keras.layers.Dense(10)
        ])
        model.compile(optimizer='adam', 
                        loss=tf.losses.SparseCategoricalCrossentropy(from_logits=True), 
                        metrics=['accuracy']) 
        return model 
        """
        exec (string_model, None, globals())
        # Create a basic model instance
        model = create_model()
        
        FILE_NAME = "test.h5"
    
        model.save(FILE_NAME)

        from django.core.files import File
        from django.core.files.uploadedfile import SimpleUploadedFile

        
        file = File(open(FILE_NAME, 'rb'))
        uploaded_file = SimpleUploadedFile('test.h5', file.read(), content_type='multipart/form-data')
        
        results = {
                'id': self.resultID,
                'train_loss_hist': "0.12, 0.01",
                'train_acc_hist':  '0.92, 0.95',
                'val_loss': 0.12,
                'val_acc': 0.95,
        }
        
        data = {
            'trained_model': uploaded_file,
            'data' : json.dumps(results)
        }
        resp = self.client.post("/results/"+str(self.resultID), data, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        filepath = os.path.join(settings.MEDIA_ROOT, settings.TRAINED_MODELS_DIR)+str(self.resultID)+'.h5'
        self.assertTrue(os.path.exists(filepath))
        
        self.obj = TrainingResult.objects.get(id=self.resultID)

        self.assertEqual(self.obj.status, 'finished')
        
        epsilon=1*10**(-8)

        self.assertEqual(self.obj.train_loss_hist, results['train_loss_hist'])
        self.assertEqual(self.obj.train_acc_hist, results['train_acc_hist'])
        self.assertTrue(abs(float(self.obj.val_loss)- results['val_loss'])<= epsilon)
        self.assertTrue(abs(float(self.obj.val_acc )- results['val_acc'])<= epsilon)

        os.remove(FILE_NAME)