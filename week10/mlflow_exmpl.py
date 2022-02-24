import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
plt.style.use('ggplot')

import torch

print(torch.__version__)

import torch.nn as nn # содержит функции для реалзации архитектуры нейронных сетей
import torch.optim as optim
import torch.utils.data as data_utils

from pytorch_lightning.metrics import Accuracy

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.preprocessing import StandardScaler

import mlflow


INPUT_SIZE = 37
HIDDEN_SIZE = 25
OUTPUT_SIZE = 4
LEARNING_RATE = 1e-2
EPOCHS = 400
BATCH_SIZE = 256


def load_dataset():
    X = pd.read_csv('./data/X_cat.csv', sep='\t', index_col=0)
    target = pd.read_csv('./data/y_cat.csv', sep='\t', index_col=0, names=['status'])  # header=-1,

    print(X.shape)
    print(X.head())

    target = target.iloc[:, :].values
    target[target == 'Died'] = 'Euthanasia'

    le = LabelEncoder()
    y = le.fit_transform(target)

    return X, y


def create_data_loader(X, y):
    X_train, X_test, y_train, y_test = train_test_split(X.values, y,
                                                        test_size=0.2, stratify=y, random_state=42)

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    train_tensor = data_utils.TensorDataset(torch.tensor(X_train.astype(np.float32)), torch.tensor(y_train))
    train_loader = data_utils.DataLoader(dataset=train_tensor,
                                         batch_size=BATCH_SIZE,
                                         shuffle=True)

    test_tensor = data_utils.TensorDataset(torch.tensor(X_test.astype(np.float32)), torch.tensor(y_test))
    test_loader = data_utils.DataLoader(dataset=test_tensor,
                                        batch_size=BATCH_SIZE,
                                        shuffle=False)

    return X_train, X_test, y_train, y_test, train_loader, test_loader

class MLPNet(nn.Module):

    def __init__(self, input_size, hidden_size, output_size):
        super(MLPNet, self).__init__()

        self.linear1 = torch.nn.Linear(input_size, hidden_size)

        self.linear2 = torch.nn.Linear(hidden_size, hidden_size)

        self.linear3 = torch.nn.Linear(hidden_size, output_size)

    def forward(self, x):
        output = self.linear1(x)
        output = torch.relu(output)

        output = self.linear2(output)
        output = torch.relu(output)

        output = self.linear3(output)
        predictions = torch.softmax(output, dim=1)

        return predictions


def run_train(train_loader, test_loader):
    model = MLPNet(INPUT_SIZE, HIDDEN_SIZE, OUTPUT_SIZE)

    criterion = nn.CrossEntropyLoss()
    accuracy = Accuracy()
    optimizer = optim.SGD(model.parameters(), lr=LEARNING_RATE)

    step = 0
    for epoch in range(EPOCHS):
        model.train()

        for features, label in train_loader:
            # Reset gradients
            optimizer.zero_grad()

            output = model(features)
            # Calculate error and backpropagate
            loss = criterion(output, label)
            loss.backward()
            acc = accuracy(output, label).item()

            # Update weights with gradients
            optimizer.step()

            mlflow.log_metric('Train/CrossEntropyLoss', loss.item(), step)
            mlflow.log_metric('Train/Accuracy', acc, step)

            step += 1

            if step % 50 == 0:
                print('EPOCH %d STEP %d : train_loss: %f train_acc: %f' %
                      (epoch, step, loss, acc))


        # Run validation
        running_loss = []
        valid_scores = []
        valid_labels = []
        model.eval()
        with torch.no_grad():
            for features, label in test_loader:
                output = model(features)
                # Calculate error and backpropagate
                loss = criterion(output, label)

                running_loss.append(loss.item())
                valid_scores.extend(torch.argmax(output, dim=1))
                valid_labels.extend(label)

        valid_accuracy = accuracy(torch.tensor(valid_scores), torch.tensor(valid_labels)).item()

        mlflow.log_metric('Valid/CrossEntropyLoss', np.mean(running_loss), step)
        mlflow.log_metric('Valid/Accuracy', valid_accuracy, step)

        print('EPOCH %d : valid_loss: %f valid_acc: %f' % (epoch, np.mean(running_loss), valid_accuracy))

    return

def run_experiment():
    features, labels = load_dataset()
    X_train, X_test, y_train, y_test, train_loader, test_loader = create_data_loader(features, labels)

    mlflow.log_param("LEARNING_RATE", LEARNING_RATE)
    mlflow.log_param("INPUT_SIZE", INPUT_SIZE)
    mlflow.log_param("HIDDEN_SIZE", HIDDEN_SIZE)
    mlflow.log_param("NROF_CLASSES", OUTPUT_SIZE)
    mlflow.log_param("BATCH_SIZE", BATCH_SIZE)

    run_train(train_loader, test_loader)

    return

with mlflow.start_run(run_name='MLFlow_experiment'):
    mlflow.log_artifact("mlflow_exmpl.py")
    run_experiment()