export class Deployment {
    batch: number;
    tf_kwargs_fit: string;
    tf_kwargs_val: string;
    pth_kwargs_fit: string;
    pth_kwargs_val: string;
    conf_mat_settings: boolean;
    configuration: number;
    gpumem: number;
    optimizer: string;
    learning_rate: number;
    loss: string;
    metrics: string;
    incremental: boolean;
    indefinite: boolean;
    stream_timeout: number;
    message_poll_timeout: number;
    monitoring_metric: string;
    change: string;
    improvement: number;
    numeratorBatch: number;
    denominatorBatch: number;
}