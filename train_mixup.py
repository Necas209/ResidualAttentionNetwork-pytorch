import time

import numpy as np
import torch.nn as nn
from torch.utils.data import Dataset

# from model.residual_attention_network_pre import ResidualAttentionModel
# based https://github.com/liudaizong/Residual-Attention-Network
from residual_attention_network import ResidualAttentionModel92U as ResidualAttentionModel
from utils import *

classes = ('plane', 'car', 'bird', 'cat', 'deer',
           'dog', 'frog', 'horse', 'ship', 'truck')


def train(model: ResidualAttentionModel, train_loader: torch.utils.data.DataLoader,
          criterion: nn.CrossEntropyLoss, optimizer: torch.optim.SGD, epoch: int, args: Namespace):
    """Train for one epoch on the training set"""
    batch_time = AverageMeter()
    losses = AverageMeter()
    top1 = AverageMeter()
    total = 0
    correct = 0

    if epoch > 300:
        is_mixup = False
    else:
        is_mixup = True

    # switch to train mode
    model.train()

    end = time.perf_counter()
    for i, (images, labels) in enumerate(train_loader):
        images = images.cuda()
        labels = labels.cuda(non_blocking=True)

        output = torch.Tensor()
        if is_mixup:
            images, targets_a, targets_b, lam = mixup_data(images, labels, alpha=1.0)
            # ForwardProp
            output = model(images)
            loss = mixup_criterion(criterion, output, targets_a, targets_b, lam)
            # measure accuracy and record loss
            _, predicted = torch.max(output.data, 1)
            total += images.size(0)
            correct += lam * predicted.eq(targets_a.data).sum() + (1 - lam) * predicted.eq(targets_b.data).sum()
            prec1 = 100 * correct / total
        else:
            # ForwardProp
            output = model(images)
            loss = criterion(output, labels)
            # measure accuracy and record loss
            prec1 = accuracy(output.data, labels, topk=(1,))[0]

        # update variables
        losses.update(loss.data, images.size(0))
        top1.update(prec1, images.size(0))

        # BackProp + Optimize
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        # measure elapsed time
        batch_time.update(time.perf_counter() - end)
        end = time.perf_counter()

        if i % args.print_freq == 0:
            print(f'Epoch: [{epoch}][{i}/{len(train_loader)}]\t'
                  f'Time {batch_time.val:.3f} ({batch_time.avg:.3f})\t'
                  f'Loss {losses.val:.4f} ({losses.avg:.4f})\t'
                  f'Prec@1 {top1.val:.3f} ({top1.avg:.3f})')
    # log to TensorBoard
    if args.tensorboard:
        log_value('train_loss', losses.avg, epoch)
        log_value('train_acc', top1.avg, epoch)


def validate(model: ResidualAttentionModel, val_loader: torch.utils.data.DataLoader,
             criterion: nn.CrossEntropyLoss, epoch: int, args: Namespace):
    """Perform validation on the validation set"""
    batch_time = AverageMeter()
    losses = AverageMeter()
    top1 = AverageMeter()

    # switch to evaluate mode
    model.eval()

    end = time.perf_counter()
    for i, (inp, target) in enumerate(val_loader):
        target: torch.Tensor = target.cuda(non_blocking=True)
        inp: torch.Tensor = inp.cuda()

        # compute output
        with torch.no_grad():
            output: torch.Tensor = model(inp)
            loss: torch.Tensor = criterion(output, target)

        # measure accuracy and record loss
        prec1: torch.Tensor = accuracy(output.data, target, topk=(1,))[0]
        losses.update(loss.data, inp.size(0))
        top1.update(prec1, inp.size(0))

        # measure elapsed time
        batch_time.update(time.perf_counter() - end)
        end = time.perf_counter()

        if i % args.print_freq == 0:
            print(f'Test: [{i}/{len(val_loader)}]\t'
                  f'Time {batch_time.val:.3f} ({batch_time.avg:.3f})\t'
                  f'Loss {losses.val:.4f} ({losses.avg:.4f})\t'
                  f'Prec@1 {top1.val:.3f} ({top1.avg:.3f})')

    print(' * Prec@1 {top1.avg:.3f}'.format(top1=top1))
    # log to TensorBoard
    if args.tensorboard:
        log_value('val_loss', losses.avg, epoch)
        log_value('val_acc', top1.avg, epoch)
    return top1.avg


def test(model: ResidualAttentionModel, test_loader: torch.utils.data.DataLoader):
    """Perform testing on the test set"""
    top1 = AverageMeter()

    model.eval()

    correct = 0
    total = 0
    class_correct = list(0. for _ in range(10))
    class_total = list(0. for _ in range(10))

    for images, labels in test_loader:
        images: torch.Tensor = images.cuda()
        labels: torch.Tensor = labels.cuda(non_blocking=True)

        with torch.no_grad():
            outputs: torch.Tensor = model(images)

        _, predicted = torch.max(outputs.cuda().data, 1)
        prec1: torch.Tensor = accuracy(outputs.data, labels, topk=(1,))[0]
        top1.update(prec1, images.size(0))

        total += labels.size(0)
        correct += (predicted == labels.data).sum()
        #
        c = (predicted == labels.data).squeeze()
        for i in range(16):
            label = labels.data[i]
            class_correct[label] += c[i]
            class_total[label] += 1

    print(f'Accuracy of the model on the test images: {top1.avg:.2f}%')
    for i in range(10):
        print(f'Accuracy of {classes[i]} : {100 * class_correct[i] / class_total[i]: .2f}%')


def mixup_data(x, y, alpha=1.0):
    """Returns mixed inputs, pairs of targets, and lambda"""
    if alpha > 0:
        lam = np.random.beta(alpha, alpha)
    else:
        lam = 1

    batch_size = x.size()[0]
    index = torch.randperm(batch_size).cuda()

    mixed_x = lam * x + (1 - lam) * x[index, :]
    y_a, y_b = y, y[index]
    return mixed_x, y_a, y_b, lam


def mixup_criterion(criterion, pred, y_a, y_b, lam):
    return lam * criterion(pred, y_a) + (1 - lam) * criterion(pred, y_b)
