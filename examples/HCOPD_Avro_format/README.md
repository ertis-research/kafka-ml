# HCOPD
Classification of Saliva Samples of Healthy Control (HC) and COPD -- HCOPD 

This repository introduces a novel dataset for the classification of Chronic Obstructive Pulmonary Disease (COPD) patients and Healthy Controls. The Exasens dataset includes demographic information on 4 groups of saliva samples (COPD-HC-Asthma-Infected) collected in the frame of a joint research project, Exasens (https://www.leibniz-healthtech.de/en/research/projects/bmbf-project-exasens/), at the Research Center Borstel, BioMaterialBank Nord (Borstel, Germany). The sampling procedure of the patient materials was approved by the local ethics committee of the University of Luebeck under the approval number AZ-16-167 and a written informed consent was obtained from all subjects. A permittivity biosensor, developed at IHP Microelectronics (Frankfurt Oder, Germany), was used for the dielectric characterization of the saliva samples for classification purposes (https://doi.org/10.3390/healthcare7010011). 

The following TensorFlow model has been used in Kafka-ML for this dataset:

```
model = tf.keras.Sequential([
    tf.keras.layers.Dropout(0.2, input_shape=(3,)),  
    tf.keras.layers.Dense(4, activation='sigmoid'),
    tf.keras.layers.Dense(2, activation='softmax')
])
model.compile(keras.optimizers.Adam(lr=.0001), loss='sparse_categorical_crossentropy', metrics=['accuracy'])
```
The batch_size used is 10, the training configuration (steps=1000, shuffle=True) and evaluation configuration (steps=5).

Definition of 4 sample groups included within the Exasens dataset: 

(I) Outpatients and hospitalized patients with COPD without acute respiratory infection (COPD). 

(II) Outpatients and hospitalized patients with asthma without acute respiratory infections (Asthma). 

(III) Patients with respiratory infections, but without COPD or asthma (Infected). 

(IV) Healthy controls without COPD, asthma, or any respiratory infection (HC).

Attribute Information: 

1- Diagnosis (COPD-HC-Asthma-Infected) 

2- ID 

3- Age

4- Gender (1=male, 0=female) 

5- Smoking Status (1=Non-smoker, 2=Ex-smoker, 3=Active-smoker) 

In case of using the introduced Exasens dataset or the proposed classification methods, please cite the following papers: 
- P. S. Zarrin, N. Roeckendorf, and C. Wenger. In-vitro Classification of Saliva Samples of COPD Patients and Healthy Controls Using Non-perceptron Machine Learning Tools. Annals of biomedical engineering, 2020. 

- Soltani Zarrin, P.; Ibne Jamal, F.; Roeckendorf, N.; Wenger, C. Development of a Portable Dielectric Biosensor for Rapid Detection of Viscosity Variations and Its In Vitro Evaluations Using Saliva Samples of COPD Patients and Healthy Control. Healthcare 2019, 7, 11.

- Soltani Zarrin, P.; Jamal, F.I.; Guha, S.; Wessel, J.; Kissinger, D.; Wenger, C. Design and Fabrication of a BiCMOS Dielectric Sensor for Viscosity Measurements: A Possible Solution for Early Detection of COPD. Biosensors 2018, 8, 78.

- P.S. Zarrin and C. Wenger. Pattern Recognition for COPD Diagnostics Using an Artificial Neural Network and Its Potential Integration on Hardware-based Neuromorphic Platforms. Springer Lecture Notes in Computer Science (LNCS), Vol. 11731, pp. 284-288, 2019.   

- Krause, T., Ramaker, K., Röckendorf, N., Sinnecker, H. and Frey, A., 2016. Airway mucins–suitable biomarkers to predict an upcoming exacerbation in COPD and asthma?. Pneumologie, 70(07), p.P43.
