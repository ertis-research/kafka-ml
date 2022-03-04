export class SimpleModel {
  id: number;
  name: string;
}

export class MLModel {
  id: number;
  name: string;
  description: string;
  imports: string;
  code: string;
  distributed: boolean;
  father: SimpleModel;
  framework: string;
}