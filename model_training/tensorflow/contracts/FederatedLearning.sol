// SPDX-License-Identifier: MIT
pragma solidity ^0.8.6;
pragma experimental ABIEncoderV2;

/// @title Records contributions made in a Kafka-ML Federated Learning process
/// @author Antonio Jesus Chaves Garcia - ERTIS Research Group - University of Malaga
contract FederatedLearning {
    /// @notice Only the evaluator can call a function with this modifier.
    modifier evaluatorOnly() {
        require(tx.origin == evaluator, "Not the registered evaluator");
        _;
    }

    /// @notice Event emitted when a KafkaModel is enqueued or dequeued
    event set_global_model(uint256 round, string model);
    event add_update_to_queue(address client, string model, string metrics);
    event dequeue_model_update(string value, uint256 round);
    event global_update_relationship(string globalModel, string kafkaModel);
    event set_tokens_to_update(string kafkaModel, uint256 tokens);

    /// @notice Address of contract creator, who evaluates updates
    address public evaluator;

    /// @notice The timestamp when the genesis model was uploaded
    uint256 internal startTrainingTimestamp;

    uint256 internal stopTrainingTimestamp;
    bool internal isTrainingActive = true;

    /// @notice Current round of training
    uint256 internal currentRound = 0;

    /// @notice Training Settings
    string internal trainingSettings;

    /// @notice Model Architecture;
    string internal modelArchitecture;

    /// @notice Model Compile Args;
    string internal modelCompileArgs;

    /// @notice Global model for each round
    mapping(uint256 => string) internal globalmodel;
    
    /// @notice Given a global model, which KafkaModel has been used to generate the new one;
    mapping(string => string) internal globalModelToUpdate;

    /// @notice Queue for Kafka messages (updates) and associated mappings
    mapping(uint256 => string) internal agg_model_queue;
    mapping(string => string) internal agg_model_metrics;
    mapping(string => uint256) internal agg_model_data_amount;
    mapping(string => address) internal agg_model_accounts;

    /// @notice Mapping of updates from each address
    mapping(address => string[]) internal updatesFromAddress;

    /// @notice Front and last of the queue
    uint256 internal q_front;
    uint256 internal q_last;

    /// @notice Whether or not each model update has been evaluated
    mapping(string => bool) internal tokensAssigned;

    /// @dev The contributivity score for each address, if evaluated
    mapping(string => uint256) internal tokens;

    /// @notice Constructor. The address that deploys the contract is set as the evaluator.
    constructor() {
        q_front = 1;
        q_last = 0;
        evaluator = tx.origin;
    }

    /// @notice Get the timestamp when the training started
    function getStartTrainingTimestamp() external view returns (uint256) {
        return startTrainingTimestamp;
    }

    /// @notice Get the timestamp when the training stopped
    function getStopTrainingTimestamp() external view returns (uint256) {
        return stopTrainingTimestamp;
    }

    /// @notice Get the status of the training
    function getTrainingStatus() external view returns (bool) {
        return isTrainingActive;
    }

    function stopTraining() external evaluatorOnly {
        stopTrainingTimestamp = block.timestamp;
        isTrainingActive = false;
    }

    /// @notice Get the current round of training
    function getCurrentRound() external view returns (uint256) {
        return currentRound;
    }

    /// @notice Saves training and model settings into the contract
    function saveTrainingSettings(
        string calldata _trainingSettings,
        string calldata _modelArchitecture,
        string calldata _modelCompileArgs
    ) external evaluatorOnly {
        trainingSettings = _trainingSettings;
        modelArchitecture = _modelArchitecture;
        modelCompileArgs = _modelCompileArgs;
    }

    /// @notice Save the KafkaModel that has been used to generate the new global model
    function saveGlobalModelToUpdate(
        string calldata kafkaModel,
        string calldata globalModel
    ) external evaluatorOnly {
        globalModelToUpdate[globalModel] = kafkaModel;
        emit global_update_relationship(globalModel, kafkaModel);
    }

    /// @notice Get the KafkaModel that has been used to generate the new global model
    function getGlobalModelToUpdate(
        string calldata globalModel
    ) external view returns (string memory) {
        return globalModelToUpdate[globalModel];
    }

    /// @notice Get the training settings
    function getTrainingSettings() external view returns (string memory) {
        return trainingSettings;
    }

    /// @notice Get the model architecture
    function getModelArchitecture() external view returns (string memory) {
        return modelArchitecture;
    }

    /// @notice Get the model compile arguments
    function getModelCompileArgs() external view returns (string memory) {
        return modelCompileArgs;
    }

    /// @notice Save the global model for a given round of training
    function saveGlobalModel(
        string calldata kafkaModel,
        uint256 _round
    ) external evaluatorOnly {
        if (currentRound == 0) {
            startTrainingTimestamp = block.timestamp;
        }
        currentRound = _round;
        globalmodel[currentRound] = kafkaModel;
        emit set_global_model(currentRound, kafkaModel);
    }

    /// @notice Get the global model for a given round of training
    function getGlobalModel(
        uint256 _round
    ) external view returns (string memory) {
        return globalmodel[_round];
    }

    /// @notice Enqueue a Kafka message (update) to the queue
    function enqueue(string calldata data) internal {
        q_last += 1;
        agg_model_queue[q_last] = data;
    }

    /// @notice Dequeue a Kafka message (update) from the queue and return it
    function dequeue() internal evaluatorOnly returns (string memory res) {
        require(q_last >= q_front); // non-empty queue
        emit dequeue_model_update(agg_model_queue[q_front], currentRound);

        res = agg_model_queue[q_front];

        delete agg_model_queue[q_front];
        q_front += 1;
    }

    /// @notice Get the front value of the queue
    function getSize() external view returns (uint256) {
        if (q_last < q_front) {
            return 0; // Queue is empty
        } else {
            return (q_last - q_front + 1);
        }
    }

    /// @notice Records a training contribution in the current round.
    function sendClientContribution(
        string calldata kafkaModel,
        string calldata metrics,
        uint256 data_amount
    ) external {
        emit add_update_to_queue(tx.origin, kafkaModel, metrics);
        enqueue(kafkaModel);
        agg_model_metrics[kafkaModel] = metrics;
        agg_model_accounts[kafkaModel] = tx.origin;
        updatesFromAddress[tx.origin].push(kafkaModel);
        agg_model_data_amount[kafkaModel] = data_amount;
    }

    function dequeueModel() external {
        dequeue();
    }

    function getQueueFirstElement() external view returns (string memory) {
        require(q_last - q_front + 1 > 0, "Queue is empty");
        return agg_model_queue[q_front];
    }

    /// @notice Get the metrics of a Kafka message (update)
    function getModelMetrics(
        string calldata model
    ) external view returns (string memory) {
        return agg_model_metrics[model];
    }

    /// @notice Get the account of a Kafka message (update)
    function getModelAccount(
        string calldata model
    ) external view returns (address) {
        return agg_model_accounts[model];
    }

    /// @notice Get the account of a Kafka message (update)
    function getModelDataSize(
        string calldata model
    ) external view returns (uint256) {
        return agg_model_data_amount[model];
    }

    function getMetricsByRound(
        uint256 round
    ) external view returns (string memory) {
        string memory model = globalmodel[round];
        return agg_model_metrics[globalModelToUpdate[model]];
    }

    function getParticipants() external view returns (address[] memory) {
        address[] memory participants = new address[](currentRound);
        for (uint256 i = 1; i <= currentRound; i++) {
            string memory model = globalmodel[i];
            participants[i-1] = agg_model_accounts[globalModelToUpdate[model]];
        }
        return participants;
    }

    function getReward(
        address _address
    ) external view returns (uint256) {
        string [] memory updates = updatesFromAddress[_address];
        uint256 reward = 0;
        for (uint256 i = 0; i < updates.length; i++) {
            reward += tokens[updates[i]];
        }
        return reward;
    }

    /// @notice Assigns a token count to an update.
    /// @param kafkaModel The KafkaModel of the update
    /// @param _numTokens The number of tokens to award; should be based on marginal value contribution
    function setTokens(
        string calldata kafkaModel,
        uint256 _numTokens
    ) external evaluatorOnly {
        require(
            !tokensAssigned[kafkaModel],
            "Update has already been rewarded"
        );
        tokens[kafkaModel] = _numTokens;
        tokensAssigned[kafkaModel] = true;

        emit set_tokens_to_update(kafkaModel, _numTokens);
    }

    /// @notice Count the tokens for a given address.abi
    /// @param _address The address to count tokens for
    /// @return count The number of tokens the address has earned
    function countTokens(
        address _address
    ) external view returns (uint256 count) {
        string[] memory updates = updatesFromAddress[_address];
        for (uint256 i = 0; i < updates.length; i++) {
            count += tokens[updates[i]];
        }
    }
}
