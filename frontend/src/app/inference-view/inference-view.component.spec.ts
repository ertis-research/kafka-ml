import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { InferenceViewComponent } from './inference-view.component';

describe('InferenceViewComponent', () => {
  let component: InferenceViewComponent;
  let fixture: ComponentFixture<InferenceViewComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ InferenceViewComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(InferenceViewComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
