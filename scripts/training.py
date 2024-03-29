import torch, os, pickle, logging

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from collections import namedtuple

from torch.utils.data import DataLoader

import utils.model_and_training as utils


def show_history(train_history, valid_history, title = None, outputfile = None):
    assert len(train_history) == len(valid_history)
    
    x = list(range(1, len(train_history)+1))
    
    fig, ax = plt.subplots(figsize=(10,6))
    ax.plot(x, train_history, label = 'Training')
    ax.plot(x, valid_history, label = 'Validation')
    ax.set_xlabel('Epoch')
    ax.set_ylabel(title)
    ax.set_title(title)
    ax.legend()
    ax.grid(axis = 'y', linestyle = '--')
    ax.set_axisbelow(True)
    plt.tight_layout()
    if outputfile:
        plt.savefig(outputfile, bbox_inches = 'tight')
    plt.show()

def onehot_to_image(array: np.ndarray):
  """
  """
  channel_to_color = {0: [255, 255, 255], #invalid pairing = white
                      1: [64, 64, 64], #unpaired = gray
                      2: [0, 255, 0], #GC = green
                      3: [0, 128, 0], #CG = dark green
                      4: [0, 0, 255], #UG = blue
                      5: [0, 0, 128], #GU = dark blue
                      6: [255, 0, 0], #UA = red
                      7: [128, 0, 0]} #AU = dark red

  rgb_image = np.zeros((array.shape[0], array.shape[1], 3), dtype=np.uint8)

  for channel, color in channel_to_color.items():
    # Select the indices where the channel has non-zero values
    indices = array[:, :, channel] > 0
    # Assign the corresponding color to those indices in the RGB image
    rgb_image[indices] = color

  return rgb_image

def show_matrices(inputs, observed, predicted, treshold=0.5, output_file = None):
  """
  """
  fig, axs = plt.subplots(1, 4, figsize=(6,2))
  
  axs[0].imshow(onehot_to_image(inputs.permute(0, 2, 3, 1).squeeze().detach().cpu().numpy()))
  axs[0].set_title("Input")

  axs[1].imshow(observed.permute(0, 2, 3, 1).squeeze().detach().cpu().numpy(), cmap='binary')
  axs[1].set_title("Observed")

  axs[2].imshow(predicted.permute(0, 2, 3, 1).squeeze().detach().cpu().numpy(), cmap='binary')
  axs[2].set_title("Predicted")

  predicted_binary = (predicted.permute(0, 2, 3, 1).squeeze().detach().cpu() >= treshold).float()
  axs[3].imshow(predicted_binary, cmap='binary')
  axs[3].set_title("Predicted binary")

  plt.tight_layout()

  if output_file:
    plt.savefig(output_file)
  else:
    plt.show()

  plt.close()


def fit_model(model, train_dataset, validtion_dataset, patience = 5, lr = 0.01, weigth_decay = 0, optimizer =utils.adam_optimizer, loss_function = utils.dice_loss, epochs = 50, batch_size = 1): 
    """
    """
    best_score = float('inf')
    early_stopping_counter = 0
    
    train_dl = DataLoader(train_dataset, batch_size = batch_size, shuffle = True)
    valid_dl = DataLoader(validtion_dataset, batch_size = batch_size)

    opt = optimizer(model, lr, weigth_decay)

    train_loss_history, train_F1_history, valid_loss_history, valid_F1_history = [], [], [], []

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    model.to(device)

    logging.info(f"Training model with {len(train_dl)} training samples and {len(valid_dl)} validation samples. Device: {device}")

    for epoch in range(epochs): 
        running_loss, running_F1 = 0.0, 0.0
        model.train()

        for input, target in train_dl: 
            input, target = input.to(device), target.to(device).unsqueeze(1) #Since the model expects a channel dimension target needs to be unsqueezed

            #Forward pass
            opt.zero_grad()
            output = model(input)

            loss = loss_function(output, target)
            
            #Backward pass
            loss.backward()
            opt.step()

            running_loss += loss.item()
            running_F1 += utils.f1_score(output, target).item()
        
        #Validation loss (only after each epoch)
        valid_loss, valid_F1 = 0.0, 0.0
        with torch.no_grad():
            for valid_input, valid_target in valid_dl: 
                valid_input, valid_target = valid_input.to(device), valid_target.to(device).unsqueeze(1)

                valid_output = model(valid_input)
                valid_loss += loss_function(valid_output, valid_target).item()
                valid_F1 += utils.f1_score(valid_output, valid_target).item()
        
        val_loss = valid_loss/len(valid_dl)
        
        train_loss_history.append(running_loss/len(train_dl))
        train_F1_history.append(running_F1/len(train_dl))
        valid_loss_history.append(val_loss)
        valid_F1_history.append(valid_F1/len(valid_dl))

        logging.info(f"Epoch {epoch+1}/{epochs}: Train loss: {train_loss_history[-1]:.4f}, Train F1: {train_F1_history[-1]:.4f}, Validation loss: {valid_loss_history[-1]:.4f}, Validation F1: {valid_F1_history[-1]:.4f}")
        if epoch > 0:
            show_history(train_loss_history, valid_loss_history, title = 'Loss', outputfile = 'training_log/loss_history.png')
            show_history(train_F1_history, valid_F1_history, title = 'F1 score', outputfile = 'training_log/F1_history.png')
        
        show_matrices(input, target, output, output_file = 'training_log/matrix_example.png')

        if val_loss < best_score:
           best_score = val_loss
           early_stopping_counter = 0
           #Save model
           torch.save(model.state_dict(), 'RNA_Unet.pth')
        else: 
           early_stopping_counter += 1
        
        logging.info(f'This epoch: {val_loss}. Best: {best_score}. Epochs without improvement {early_stopping_counter}.\n')

        #Check early stopping condition
        if early_stopping_counter >= patience: 
            logging.info(f'EARLY STOPPING TRIGGERED: No improvement in {patience} epochs. Stopping training.')
            break
    

    data = {"train_loss": train_loss_history, "train_F1": train_F1_history, "valid_loss": valid_loss_history, "valid_F1": valid_F1_history}
    df = pd.DataFrame(data)
    df.to_csv('results/training_history.csv')



if __name__ == "__main__":
    os.makedirs('training_log', exist_ok=True)
    logging.basicConfig(filename='training_log/training_log.txt', level=logging.INFO)
    
    train = pickle.load(open('data/train.pkl', 'rb'))
    valid = pickle.load(open('data/val.pkl', 'rb'))

    RNA_data = namedtuple('RNA_data', 'input output length family name pairs')

    train_dataset = utils.ImageToImageDataset(train)
    valid_dataset = utils.ImageToImageDataset(valid)

    model = utils.RNA_Unet()

    fit_model(model, train_dataset, valid_dataset, epochs=1)