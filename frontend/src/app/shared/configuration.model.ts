export class SimpleModel {
  id: number;
  name: string;
}

export class Configuration {
    id: number;
    name: string;
    description: string;
    ml_models : SimpleModel[];
}