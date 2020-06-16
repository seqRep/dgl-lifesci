# -*- coding: utf-8 -*-
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Link prediction with GCN model for graphs.


import torch
import torch.nn as nn
import torch.nn.functional as F

from dgl.nn.pytorch import GraphConv

class GCN(nn.Module):
    r"""GCN from `Semi-Supervised Classification with Graph Convolutional Networks
    <https://arxiv.org/abs/1609.02907>`__

    Parameters
    ----------
    in_feats : int
        Number of input node features.
    n_hidden : int
        Number of units in the hidden layers.
    out_feats : int
        Number of out node features.
    num_layers : int
        Number of GCN layers.
    dropout : float
        The probability for dropout.
        By default, no dropout is performed for input layer.
    """

    def __init__(self,
                 in_feats,
                 n_hidden,
                 out_feats,
                 num_layers,
                 dropout):
        super(GCN, self).__init__()

        self.layers = nn.ModuleList()
        # input layer
        self.layers.append(GraphConv(in_feats, n_hidden, activation=F.relu))
        # hidden layers
        for i in range(num_layers - 2):
            self.layers.append(GraphConv(n_hidden, n_hidden, activation=F.relu))
        # output layer
        self.layers.append(GraphConv(n_hidden, out_feats, activation=None))

        self.dropout = nn.Dropout(p=dropout)

    def reset_parameters(self):
        # Reset the parameters of the GCN layers
        for layer in self.layers:
            layer.reset_parameters()

    def forward(self, g, feats):
        """Update node representations.

        Parameters
        ----------
        g : DGLGraph
            DGLGraph for a batch of graphs
        feats : FloatTensor of shape (N, M1)
            * N is the total number of nodes in the batch of graphs
            * M1 is the input node feature size, which equals in_feats in initialization

        Returns
        -------
        feats : FloatTensor of shape (N, M2)
            * N is the total number of nodes in the batch of graphs
            * M2 is the output node representation size, which equals
              out_feats in initialization.
        """
        for i, layer in enumerate(self.layers):
            if i != 0:
                feats = self.dropout(feats)
            feats = layer(g, feats)
        return feats

class GCNLinkPredictor(nn.Module):
    """Link prediction with GCN model for graphs.

    GCN is introduced in `Semi-Supervised Classification with Graph Convolutional Networks
    <https://arxiv.org/abs/1609.02907>`__. This model is based on GCN and can be used
    for link prediction on graphs.

    After updating node representations, we feed the product of the two node representations
    of the predicted edge into the Linear layers for link prediction.

    Parameters
    ----------
    in_channels : int
        Number of channels in the input layer, which equals
        the output node representation size of the GCN model.
    hidden_channels : int
        Number of units in the hidden layers.
    num_layers : int
        Number of Linear layers.
    dropout : float
        The probability for dropout.
        By default, no dropout is performed for out layer.
    """
    def __init__(self,
                 in_channels,
                 hidden_channels,
                 num_layers,
                 dropout):
        super(GCNLinkPredictor, self).__init__()

        self.lins = nn.ModuleList()
        # input layer
        self.lins.append(nn.Linear(in_channels, hidden_channels))
        # hidden layers
        for _ in range(num_layers - 2):
            self.lins.append(nn.Linear(hidden_channels, hidden_channels))
        # out layer
        self.lins.append(nn.Linear(hidden_channels, 1))

        self.dropout = nn.Dropout(dropout)

    def reset_parameters(self):
        # Reset the parameters of the Linear layers
        for layer in self.lins:
            layer.reset_parameters()

    def forward(self, x_i, x_j):
        """Link prediction.

        Parameters
        ----------
        x_i, x_j : FloatTensor of shape (B,M2)
            * Representation of the two nodes of the predicted edge.
            * B is the number of predicted edges in the batch.
            * M2 is the node feature size.

        Returns
        -------
        lp : FloatTensor of shape (B,1)
            * The result of link prediction after sigmoid.
            * B is the number of predicted edges in the batch.
        """
        x = x_i * x_j
        for lin in self.lins[:-1]:
            x = lin(x)
            x = F.relu(x)
            x = self.dropout(x)
        x = self.lins[-1](x)
        lp = torch.sigmoid(x)
        return lp