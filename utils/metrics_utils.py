"""
FILE TO CONTAIN VARIOUS METHODS OF CALCULATING PERFORMANCE METRICS FOR DIFFERENT MODELS
"""

import os

import h5py
import numpy      as np
#import tensorflow as tf
from   sklearn    import svm
from   scipy.spatial.distance import cityblock
from   scipy.spatial.distance import euclidean


class Metrics():
    """
    A class containing methods to log and calculate classification metrics
    Methods:
        :__init__:
        :log_prediction:
        :total_classification:
        :get_accuracy:
        :get_predictions_array:
        :clear_all:
        :_save_prediction:
        :_avg_pooling_classify:
        :_last_frame_classify:
        :_svm_classify:
    """

    def __init__(self, output_dims, seq_length, logger, method, is_training, model_name, exp_name, dataset, metrics_dir='default', verbose=1, load_svm=False):
        """
        Args:
            :output_dims: Output dimensions of the model, used to verify the shape of predictions
            :logger:      The logger object that will save the testing performance.
            :method:      The metrics method to be used (svm, svm_train, avg_pooling, last_frame)
            :is_training: Boolean indicating whether the testlist or trainlist is being used.
            :model_name:  Name of the model that is being tested
            :exp_name:    Name of experiment weights that the logs will be saved under.
            :dataset:     Which dataset is currently being tested.
            :verbose:     Setting verbose command
            :load_svm:    Boolean indication whether to load saved svm testlist features or to extract them. Intended for debugging.
        """
        self.output_dims=output_dims
        self.seq_length=seq_length
        self.verbose=verbose
        self.model_name = model_name
        self.exp_name = exp_name
        self.dataset = dataset
        self.correct_predictions=0
        self.total_predictions=0
        self.predictions_array=[]
        self.logger=logger
        self.method=method
        self.step=0
        self.is_training = is_training
        self.file_name_dict = {}
        self.metrics_dir = metrics_dir

        if self.is_training:
            self.log_name = 'train'

        else:
            self.log_name = 'test'

        # END IF

        if os.path.isfile(os.path.join('results', self.model_name, self.dataset, self.exp_name, self.metrics_dir,'temp'+self.method+'.hdf5')) and (('avg_pooling' in self.method) or ('last_frame' in self.method)):
            os.remove(os.path.join('results', self.model_name, self.dataset, self.exp_name, self.metrics_dir,'temp'+self.method+'.hdf5'))

        if self.method == 'svm':
            if not os.path.isfile(os.path.join('results', self.model_name, self.dataset, self.exp_name, self.metrics_dir,'temp'+self.method+'_train.hdf5')):
                print "\nError: Temporary training features are not present to train svm. Please first evaluate this model on the training split of this dataset using metricsMethod svm_train.\n"
                exit()

        # END IF

        # Debugging, load saved train and test features for an svm without regenerating the features
        if load_svm:
            self.save_file = h5py.File(os.path.join('results', self.model_name, self.dataset, self.exp_name, self.metrics_dir,'temp'+self.method+'.hdf5'), 'r')
        else:
            self.save_file = h5py.File(os.path.join('results', self.model_name, self.dataset, self.exp_name, self.metrics_dir,'temp'+self.method+'.hdf5'), 'w')

        # END IF

    def get_accuracy(self):
        """
        Args:
            None
        Return:
            Total accuracy of classifications
        """
        return self.correct_predictions / float(self.total_predictions)


    def get_predictions_array(self):
        """
        Args:
            None
        Return:
            :predictions_array:  Array of predictions with each index containing (prediction, ground_truth_label)
        """
        return self.predictions_array


    def clear_all(self):
        """
        Clear all parameters (correct_predictions, total_predictions, predicitons_array)
        Args:
            None
        Return:
            None
        """
        self.correct_predictions = 0
        self.total_predictions = 0
        self.predictions_array = []


    def log_prediction(self, label, predictions, names, step):
        """
        Args:
            :label:            Ground truth label of the video(s) used to generate the predictions
            :predictions:      The output predictions from the model accross all batches
            :name:             The name(s) of the video(s) currently being classified
        Return:
            :current_accuracy: The current classification accuracy of all videos
                               passed through this object accross multiple calls of this method
        """
        self.step = step
        self._save_prediction(label, predictions, names)

        if self.method == 'avg_pooling':
            if len(predictions.shape) >= 2:
                predictions = np.mean(predictions, 0)
            prediction = predictions.argmax()

        elif self.method == 'last_frame':
            if len(predictions.shape) >= 2:
                predictions = predictions[-1]
            prediction = predictions.argmax()

        elif 'svm' in self.method:
            prediction = -1

        elif self.method == 'DTW':
        	prediction = -1

        elif self.method == 'extract_features':
            prediction = -1

        else:
            print "Error: Invalid classification method: ", self.method
            exit()

        # END IF

        if prediction == label:
            self.correct_predictions += 1

        # END IF

        self.total_predictions += 1
        current_accuracy = self.get_accuracy()

        if self.verbose:
            print "vidName: ",names
            print "label:  ", label
            print "prediction: ", prediction

        # END IF

        self.logger.add_scalar_value(os.path.join(self.log_name, 'acc_'+self.method), current_accuracy, step=self.step)
        return current_accuracy


    def total_classification(self):
        """
        Args:
            :label:            Ground truth label of the video(s) used to generate the predictions
            :predictions:      The output predictions from the model accross all batches
            :name:             The name(s) of the video(s) currently being classified
        Return:
            :current_accuracy: The current classification accuracy of all videos
                               passed through this object accross multiple calls of this method
        """
        if self.method == 'avg_pooling':
            accuracy = self._avg_pooling_classify()

        elif self.method == 'last_frame':
            accuracy = self._last_frame_classify()

        elif self.method == 'DTW':
            accuracy = self._DTW_classify()

        elif self.method == 'svm':
            accuracy = self._svm_classify()
            self.save_file.close()
            print 'Please now classify this model using the testing split of this dataset.'
            accuracy = -1

        elif self.method == 'svm_train':
            self.save_file.close()
            print 'Please now classify this model using the testing split of this dataset.'
            accuracy = -1

        elif self.method == 'extract_features':
            self.save_file.close()
            print 'Logged accuracies for this model are irrelevent.'
            accuracy = -1

        else:
            print "Error: Invalid classification method ", self.method
            exit()

        self.logger.add_scalar_value(os.path.join(self.log_name, 'acc_'+self.method), accuracy, step=self.step)

        return accuracy


    def _avg_pooling_classify(self):
        """
        Default argmax classification averaing the outputs of all frames
        Args:

        Return:
            :current_accuracy: The current classification accuracy of all videos
                               passed through this object accross multiple calls of this method
        """
        self.clear_all()

        model_output = []
        labels = []
        names = []

        # Load the saved model testing outputs storing each video as a new index in model_output and appending the outputs to that index
        for vid_name in self.save_file.keys():
            labels.append(self.save_file[vid_name]['Label'].value)
            temp_data = []

            for clip in self.save_file[vid_name]['Data'].keys():
                temp_data.append(self.save_file[vid_name]['Data'][clip].value)

            # END FOR

            mean_feature = np.array(temp_data)
            model_output_dimensions = len(mean_feature.shape)

            if model_output_dimensions > 2:
                mean_feature = np.mean(mean_feature, axis=tuple(range(1,model_output_dimensions-1)) )   # Average everything except the dimensions for the number of clips and the outputs

            # END IF

            # Average the outputs for the clips
            mean_feature = np.mean(mean_feature, 0)
            model_output.append(mean_feature)
            names.append(vid_name)

        # END FOR

        model_output = np.array(model_output)

        # For each video, average the predictions within clips and frames therein then take the argmax prediction and compare it to the ground truth sabel
        for index in range(len(model_output)):
            prediction = model_output[index].argmax()
            label = labels[index]
            name = names[index]

            if self.verbose:
                print "vidName: ",name
                print "label:  ", label
                print "prediction: ", prediction

            # END IF

            self.predictions_array.append((prediction, label, name))
            self.total_predictions += 1

            if int(prediction) == int(label):
                self.correct_predictions += 1

            # END IF

            current_accuracy = self.correct_predictions / float(self.total_predictions)

        # END FOR

        self.save_file.close()

        os.remove(os.path.join('results', self.model_name, self.dataset, self.exp_name, self.metrics_dir,'temp'+self.method+'.hdf5'))

        return current_accuracy


    def _last_frame_classify(self):
        """
        Classification based off of the last frame of each clip
        Args:

        Return:
            :current_accuracy: The current classification accuracy of all videos
                               passed through this object accross multiple calls of this method
        """
        self.clear_all()

        model_output = []
        labels = []
        names = []

        # Load the saved model testing outputs storing each video as a new index in model_output and appending the outputs to that index
        for vid_name in self.save_file.keys():
            labels.append(self.save_file[vid_name]['Label'].value)
            temp_data = []

            for clip in self.save_file[vid_name]['Data'].keys():
                temp_data.append(self.save_file[vid_name]['Data'][clip].value)

            # END FOR

            mean_feature = np.array(temp_data)
            model_output_dimensions = len(mean_feature.shape)

            if model_output_dimensions > 2:
                mean_feature = np.array(mean_feature)[:,-1,:]   # Extract the last frame from each clip

            # END IF

            # Average the outputs for the clips
            mean_feature = np.mean(mean_feature, 0)
            model_output.append(mean_feature)
            names.append(vid_name)

        # END FOR

        model_output = np.array(model_output)

        # For each video, select only the last frame of each clip and average the last frames then take the argmax prediction and compare it to the ground truth sabel
        for index in range(len(model_output)):
            prediction = model_output[index].argmax()
            label = labels[index]
            name = names[index]

            if self.verbose:
                print "vidName: ",name
                print "label:  ", label
                print "prediction: ", prediction

            self.predictions_array.append((prediction, label, name))
            self.total_predictions += 1
            if int(prediction) == int(label):
                self.correct_predictions += 1

            current_accuracy = self.correct_predictions / float(self.total_predictions)

        # END FOR

        self.save_file.close()

        os.remove(os.path.join('results', self.model_name, self.dataset, self.exp_name, self.metrics_dir,'temp'+self.method+'.hdf5'))

        return current_accuracy


    def _svm_classify(self):
        """
        Final classification of predictions saved to temp folder using a linear svm
        Args:
            None
        Return:
            :current_accuracy: The current classification accuracy of all videos
                               passed through this object accross multiple calls of this method
        """

        self.clear_all()

        training_output = []
        training_labels = []
        training_names = []

        train_hdf5 = h5py.File(os.path.join('results', self.model_name, self.dataset, self.exp_name, self.metrics_dir,'tempextract_features.hdf5'), 'r')#+self.method+'_train.hdf5'), 'r')

        # Load the saved model testing outputs storing each video as a new index in model_output and appending the outputs to that index
        for vid_name in train_hdf5.keys():
            training_labels.append(train_hdf5[vid_name]['Label'].value)
            temp_data = []

            for clip in train_hdf5[vid_name]['Data'].keys():
                temp_data.append(train_hdf5[vid_name]['Data'][clip].value)

            # END FOR

            mean_feature = np.array(temp_data)
            model_output_dimensions = len(mean_feature.shape)

            if model_output_dimensions > 2:
                mean_feature = np.mean(mean_feature, axis=tuple(range(1,model_output_dimensions-1)) )   # Average everything except the dimensions for the number of clips and the outputs

            # END IF

            # Average the outputs for the clips
            mean_feature = np.mean(mean_feature, 0)
            training_output.append(mean_feature)
            training_names.append(vid_name)

        # END IF

        training_output = np.array(training_output)
        output_dims = training_output.shape
        training_output = training_output/(np.linalg.norm(training_output, axis=1).reshape([output_dims[0],1]).repeat(output_dims[1],1))

        # Train svm on training set features
        classifier = svm.LinearSVC()
        classifier.fit(training_output, training_labels)

        self.clear_all()

        model_output = []
        labels = []
        names = []

        # Load the saved model testing outputs storing each video as a new index in model_output and appending the outputs to that index
        for vid_name in self.save_file.keys():
            labels.append(self.save_file[vid_name]['Label'].value)
            temp_data = []

            for clip in self.save_file[vid_name]['Data'].keys():
                temp_data.append(self.save_file[vid_name]['Data'][clip].value)

            # END FOR

            mean_feature = np.array(temp_data)
            model_output_dimensions = len(mean_feature.shape)

            if model_output_dimensions > 2:
                mean_feature = np.mean(mean_feature, axis=tuple(range(1,model_output_dimensions-1)) )   # Average everything except the dimensions for the number of clips and the outputs

            # END IF

            # Average the outputs for the clips
            mean_feature = np.mean(mean_feature, 0)
            model_output.append(mean_feature)
            names.append(vid_name)

        # END FOR

        model_output = np.array(model_output)
        output_dims = model_output.shape
        model_output = model_output/(np.linalg.norm(model_output, axis=1).reshape([output_dims[0],1]).repeat(output_dims[1],1))

        # Get testing predictions from trained svm
        predictions = classifier.predict(model_output)

        for video in range(len(predictions)):
            prediction = predictions[video]
            label = labels[video]
            name = names[video]

            if self.verbose:
                print "vidName: ",name
                print "label:  ", label
                print "prediction: ", prediction

            # END IF

            self.predictions_array.append((prediction, label, name))
            self.total_predictions += 1

            if int(prediction) == int(label):
                self.correct_predictions += 1

            # END IF

            current_accuracy = self.correct_predictions / float(self.total_predictions)

        # END FOR

        self.save_file.close()

        return current_accuracy


    def _DTW_classify(self, feature_dims=-1):
        if feature_dims < 0:
            feature_dims = self.output_dims
        feature_hdf5 = h5py.File(os.path.join('results', self.model_name, self.dataset, self.exp_name,self.metrics_dir,'tempextract_features.hdf5'), 'r')

        standard_feat = np.zeros((self.output_dims, self.seq_length,feature_dims))
        training_names = []
        #training_output = []
        training_labels = []
    	for vid_name in feature_hdf5.keys():
            Curr_label = feature_hdf5[vid_name]['Label'].value
            training_labels.append(Curr_label)

            temp_data = []
            for clip in feature_hdf5[vid_name]['Data'].keys():
            	temp_data.append(feature_hdf5[vid_name]['Data'][clip].value)
            #mean_feature = np.array(temp_data)
            feature = np.array(temp_data)

            if len(feature.shape) > 2:
                feature = np.mean(feature, 0)
            standard_feat[Curr_label, :, :] = standard_feat[Curr_label, :, :] + feature
    		#model_output_dimensions = len(mean_feature.shape)

            training_names.append(vid_name)

        training_labels = np.array(training_labels)

        training_labels, num_vids_per_label = np.unique(training_labels, return_counts=True)
        for label in range(self.output_dims):
            standard_feat[label, :, :] = standard_feat[label, :, :]/num_vids_per_label[label]

        #model_output = []
        labels = []
        names = []
        predictions = []
        #output_dims = 51
        	# Load the saved model testing outputs storing each video as a new index in model_output and appending the outputs to that index
        for vid_name in self.save_file.keys():
            labels.append(self.save_file[vid_name]['Label'].value)
            temp_data = []

            for clip in self.save_file[vid_name]['Data'].keys():
                temp_data.append(self.save_file[vid_name]['Data'][clip].value)



            feature = np.array(temp_data)
            model_output_dimensions = len(feature.shape)

            if len(feature.shape) > 2:
                feature = np.mean(feature, 0)
            cost = np.zeros(self.output_dims)
            for var in range(self.output_dims):
            	cost[var] = self.DTWdist(standard_feat[var, :, :], feature)

            predictions.append(np.argmin(cost))
            names.append(vid_name)


        for video in range(len(predictions)):
            prediction = predictions[video]
            label = labels[video]
            name = names[video]

            if self.verbose:
            	print "vidName: ",name
            	print "label:  ", label
            	print "prediction: ", prediction


        	self.predictions_array.append((prediction, label, name))
        	self.total_predictions += 1
        	if int(prediction) == int(label):
        		self.correct_predictions += 1

        current_accuracy = self.correct_predictions / float(self.total_predictions)

        # END FOR

        self.save_file.close()
        return current_accuracy

    def DTWdist(self, std_feat, feature):
    	DTW = np.zeros((len(std_feat),len(feature)))
    	for i in range(len(std_feat)):
    		DTW[i, 0] = np.inf
    	for i in range(len(std_feat)):
    		DTW[0, i] = np.inf
    	DTW[0, 0] = 0

    	for i in range(len(std_feat)):
    		for j in range(len(std_feat)):
    			cost = euclidean(std_feat[i], feature[j])
    			DTW[i, j] = cost + min(DTW[i-1,j], DTW[i,j-1], DTW[i-1, j-1])

    	return DTW[-1,-1 ]


    def _save_prediction(self, label, prediction, name):
        """
        Save a given prediction and label of a video clip to the HDF5 file under the name of that video.
        This adds the information into the HDF5 file, it gets written during _total_classification
        Args:
            :label:         Ground truth label for the current clip
            :prediction:    Output prediction from the model for the current clip
            :name:          Name of the video that the current clip belongs to
        Return:
            None
        """

        if name not in self.save_file.keys():
            g = self.save_file.create_group(name)
            g.create_group('Data')
            g['Label'] = label
            self.file_name_dict[name] = 0

        # END IF

        self.save_file[name]['Data'][str(self.file_name_dict[name])] = prediction
        self.file_name_dict[name]+=1


if __name__=="__main__":
    import pdb; pdb.set_trace()