import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { IoTDevicesViewComponent } from './iot-devices-view.component';

describe('IoTDevicesViewComponent', () => {
  let component: IoTDevicesViewComponent;
  let fixture: ComponentFixture<IoTDevicesViewComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ IoTDevicesViewComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(IoTDevicesViewComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
