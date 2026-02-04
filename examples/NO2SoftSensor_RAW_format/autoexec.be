# In cases with quantization, a global variable must be entered with the input_scale and other variables related to quantization.

def start();
    import TFL;
    import math;

    var INPUT_VARS = 4;
    var OUTPUT_VARS = 1;
    var input_buf  = bytes(-4 * INPUT_VARS);
    var output_buf = bytes(-4 * OUTPUT_VARS);

    def setup_model(model_path, output_buf);
        var model = open(model_path).readbytes();
        TFL.begin("BUF");
        TFL.load(model, output_buf, 50000);
    end;

    setup_model("model.tflite", output_buf);

    def rand_float(buffer, n_features); # Using rand float instead of reading from sensor for demonstration
        for i: 0 .. n_features-1;
            buffer.setfloat(i*4, (math.rand() % 50) * math.pi);
        end;
    end;

    def predict(input_buf, output_buf);
        TFL.input(input_buf);
        while !TFL.output(output_buf);
            tasmota.delay(100);
        end;
    end;

    def inference_fn();
        rand_float(input_buf, INPUT_VARS);
        print("Input: ");
        print(input_buf.getfloat(0));

        predict(input_buf, output_buf);
        print("Prediction: ");
        print(output_buf.getfloat(0));
        tasmota.set_timer(5000, inference_fn);
    end;

    inference_fn();
end;


var wait_startup_time = tasmota.millis() + 30000;

def wait_for_startup();
    if tasmota.time_reached(wait_startup_time);
        print("Tasmota is ready");
        start();
    else;
        print("Tasmota is not ready");
        tasmota.set_timer(5000, wait_for_startup);
    end;
end;

wait_for_startup();

