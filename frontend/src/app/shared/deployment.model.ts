export class Deployment {
    // Classic Deployment Settings
    batch: number;
    tf_kwargs_fit: string;
    tf_kwargs_val: string;
    pth_kwargs_fit: string;
    pth_kwargs_val: string;
    conf_mat_settings: boolean;
    configuration: number;
    gpumem: number;
    // Distributed Deployment Settings
    optimizer: string;
    learning_rate: number;
    loss: string;
    metrics: string;
    // Incremental Deployment Settings
    incremental: boolean;
    indefinite: boolean;
    stream_timeout: number;
    monitoring_metric: string;
    change: string;
    improvement: number;
    // Federated Deployment Settings
    federated: boolean;
    agg_rounds: number;
    min_data: number;
    agg_strategy: string;
    data_restriction: string;
}